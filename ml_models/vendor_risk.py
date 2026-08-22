"""
Vendor anomaly detection and risk assessment for GST ITC reconciliation.

The main input is a pandas DataFrame containing invoice or reconciliation
history. The module accepts the canonical reconciliation column names from
``app.py`` and persists vendor risk results into the SQLAlchemy ``vendors``
table.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Optional

import pandas as pd
from sklearn.ensemble import IsolationForest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from database.db_models import Vendor


@dataclass(frozen=True)
class RiskWeights:
    """Weights for the explainable 0-100 vendor risk score."""

    missing_invoice_rate: float = 50.0
    blocked_itc_share: float = 35.0
    mismatch_or_anomaly_rate: float = 15.0


class VendorRiskModel:
    """Detect invoice anomalies and assign risk categories by GSTIN."""

    HIGH_RISK_THRESHOLD = 70.0
    MEDIUM_RISK_THRESHOLD = 40.0

    def __init__(
        self,
        contamination: float = 0.05,
        random_state: int = 42,
        weights: Optional[RiskWeights] = None,
    ) -> None:
        if not 0 < contamination < 0.5:
            raise ValueError("contamination must be between 0 and 0.5")
        self.anomaly_model = IsolationForest(
            contamination=contamination,
            random_state=random_state,
        )
        self.weights = weights or RiskWeights()

    def detect_anomalies(self, invoice_history: pd.DataFrame) -> pd.DataFrame:
        """
        Flag unusual invoice claims or mismatches with Isolation Forest.

        The returned copy contains ``anomaly_label`` (-1 for anomaly, 1 for
        normal), ``anomaly_score`` (higher means more unusual), and
        ``is_anomaly``. The model uses taxable value, total tax, and tax
        difference when available in the reconciliation output.
        """
        if invoice_history is None or invoice_history.empty:
            return self._empty_anomaly_result(invoice_history)

        result = invoice_history.copy()
        features = pd.DataFrame(
            {
                "taxable_value": self._numeric_column(
                    result, "Taxable Value"
                ),
                "total_tax": self._total_tax(result),
                "tax_difference": self._numeric_column(
                    result, "Max Tax Diff (₹)"
                ),
            },
            index=result.index,
        ).fillna(0.0)

        if len(features) == 1:
            result["anomaly_label"] = 1
            result["anomaly_score"] = 0.0
            result["is_anomaly"] = False
            return result

        self.anomaly_model.fit(features)
        result["anomaly_label"] = self.anomaly_model.predict(features)
        result["anomaly_score"] = -self.anomaly_model.decision_function(features)
        result["is_anomaly"] = result["anomaly_label"] == -1
        return result

    def calculate_vendor_risk(self, invoice_history: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate an explainable 0-100 score for every vendor in history.

        Score components:
          * 50 points: proportion of invoices missing from GSTR-2B
          * 35 points: vendor share of all blocked ITC
          * 15 points: proportion of mismatches or detected anomalies

        Risk tiers are High (>=70), Medium (>=40), and Low (<40). The input
        may contain either reconciliation results or invoice-level records.
        """
        if invoice_history is None or invoice_history.empty:
            return pd.DataFrame(
                columns=[
                    "GSTIN",
                    "Vendor Name",
                    "total_invoices",
                    "missing_invoices",
                    "blocked_itc",
                    "mismatch_count",
                    "anomaly_count",
                    "risk_score",
                    "Risk Category",
                    "risk_level",
                ]
            )

        data = self.detect_anomalies(invoice_history)
        data["GSTIN"] = self._text_column(data, ["GSTIN", "gstin"], "UNKNOWN")
        data["Vendor Name"] = self._text_column(
            data,
            ["Vendor Name (Books)", "Vendor Name", "vendor_name"],
            "Unknown Vendor",
        )
        data["_is_missing"] = self._missing_mask(data)
        data["_blocked_itc"] = self._blocked_itc(data)
        data["_is_mismatch"] = self._status_mask(data)

        grouped = (
            data.groupby(["GSTIN", "Vendor Name"], dropna=False)
            .agg(
                total_invoices=("GSTIN", "size"),
                missing_invoices=("_is_missing", "sum"),
                blocked_itc=("_blocked_itc", "sum"),
                mismatch_count=("_is_mismatch", "sum"),
                anomaly_count=("is_anomaly", "sum"),
            )
            .reset_index()
        )

        total_blocked_itc = float(grouped["blocked_itc"].sum())
        total_weights = (
            self.weights.missing_invoice_rate
            + self.weights.blocked_itc_share
            + self.weights.mismatch_or_anomaly_rate
        )
        if total_weights <= 0:
            raise ValueError("At least one risk weight must be greater than zero")

        invoice_count = grouped["total_invoices"].clip(lower=1)
        missing_rate = (grouped["missing_invoices"] / invoice_count).clip(upper=1.0)
        blocked_share = (
            grouped["blocked_itc"] / total_blocked_itc
            if total_blocked_itc > 0
            else pd.Series(0.0, index=grouped.index)
        ).clip(upper=1.0)
        issue_rate = (
            (grouped["mismatch_count"] + grouped["anomaly_count"]) / invoice_count
        ).clip(upper=1.0)

        grouped["risk_score"] = (
            missing_rate * self.weights.missing_invoice_rate
            + blocked_share * self.weights.blocked_itc_share
            + issue_rate * self.weights.mismatch_or_anomaly_rate
        ).mul(100.0 / total_weights).round(2)
        grouped["Risk Category"] = grouped["risk_score"].map(self._risk_level)
        grouped["risk_level"] = grouped["Risk Category"]
        grouped["blocked_itc"] = grouped["blocked_itc"].round(2)
        return grouped

    def save_risk_scores(
        self,
        engine: Engine,
        risk_scores: pd.DataFrame,
        company_id: int,
    ) -> int:
        """Upsert risk scores into ``vendors`` and return rows written."""
        required_columns = {"GSTIN", "Vendor Name", "risk_score", "risk_level"}
        missing_columns = required_columns - set(risk_scores.columns)
        if missing_columns:
            raise ValueError(
                "Risk scores are missing required column(s): "
                + ", ".join(sorted(missing_columns))
            )

        written = 0
        with Session(engine) as session:
            for _, row in risk_scores.iterrows():
                gstin = str(row["GSTIN"]).strip().upper()
                if not gstin or gstin == "NAN":
                    continue

                vendor = session.scalar(
                    select(Vendor).where(
                        Vendor.company_id == company_id,
                        Vendor.gstin == gstin,
                    )
                )
                if vendor is None:
                    vendor = Vendor(
                        company_id=company_id,
                        gstin=gstin,
                        name=str(row["Vendor Name"]),
                    )
                    session.add(vendor)

                vendor.name = str(row["Vendor Name"])
                vendor.risk_score = Decimal(str(round(float(row["risk_score"]), 2)))
                vendor.risk_level = str(row["risk_level"])
                written += 1

            session.commit()
        return written

    @staticmethod
    def _risk_level(score: float) -> str:
        if score >= VendorRiskModel.HIGH_RISK_THRESHOLD:
            return "High"
        if score >= VendorRiskModel.MEDIUM_RISK_THRESHOLD:
            return "Medium"
        return "Low"

    @staticmethod
    def _numeric_column(data: pd.DataFrame, column: str) -> pd.Series:
        if column not in data.columns:
            return pd.Series(0.0, index=data.index)
        return pd.to_numeric(data[column], errors="coerce").fillna(0.0)

    def _total_tax(self, data: pd.DataFrame) -> pd.Series:
        for column in ["Blocked Tax (Rs)", "blocked_itc"]:
            if column in data.columns:
                return self._numeric_column(data, column)
        return sum(
            (self._numeric_column(data, column) for column in ["CGST", "SGST", "IGST"]),
            pd.Series(0.0, index=data.index),
        )

    def _blocked_itc(self, data: pd.DataFrame) -> pd.Series:
        missing = data["_is_missing"]
        return self._total_tax(data).where(missing, 0.0)

    @staticmethod
    def _text_column(data: pd.DataFrame, names: Iterable[str], default: str) -> pd.Series:
        for name in names:
            if name in data.columns:
                return data[name].fillna(default).astype(str).replace("", default)
        return pd.Series(default, index=data.index)

    @staticmethod
    def _missing_mask(data: pd.DataFrame) -> pd.Series:
        if "Category" not in data.columns:
            return pd.Series(False, index=data.index)
        return data["Category"].eq("Missing in GSTR-2B")

    @staticmethod
    def _status_mask(data: pd.DataFrame) -> pd.Series:
        if "Category" not in data.columns:
            return pd.Series(False, index=data.index)
        return data["Category"].eq("Value Mismatch")

    @staticmethod
    def _empty_anomaly_result(data: Optional[pd.DataFrame]) -> pd.DataFrame:
        result = data.copy() if data is not None else pd.DataFrame()
        result["anomaly_label"] = pd.Series(dtype="int64")
        result["anomaly_score"] = pd.Series(dtype="float64")
        result["is_anomaly"] = pd.Series(dtype="bool")
        return result


if __name__ == "__main__":
    print("VendorRiskModel is ready for invoice history DataFrames.")


# Backward-compatible name for existing integrations.
VendorRiskAssessment = VendorRiskModel
