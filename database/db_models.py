"""
SQLAlchemy models for the GST ITC reconciliation system.

Run this module directly to create the local SQLite database:

    python database/db_models.py

The default database file is ``database/gst_reconciliation.db``. A different
SQLite URL can be supplied to ``create_database()`` when wiring this module
into the Streamlit application or tests.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "gst_reconciliation.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"


class Base(DeclarativeBase):
    """Base class for all application models."""


class Company(Base):
    """A legal entity whose books and GSTR-2B data are reconciled."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    gstin: Mapped[Optional[str]] = mapped_column(String(15), unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    vendors: Mapped[list["Vendor"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    reconciliation_runs: Mapped[list["ReconciliationRun"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    reconciliation_results: Mapped[list["ReconciliationResult"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class Vendor(Base):
    """A supplier registered against a company."""

    __tablename__ = "vendors"
    __table_args__ = (
        UniqueConstraint("company_id", "gstin", name="uq_vendor_company_gstin"),
        Index("ix_vendors_company_name", "company_id", "name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    gstin: Mapped[str] = mapped_column(String(15), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    risk_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    risk_level: Mapped[Optional[str]] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    company: Mapped["Company"] = relationship(back_populates="vendors")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="vendor")


class Invoice(Base):
    """An invoice imported from either Books or GSTR-2B."""

    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "source",
            "gstin",
            "invoice_number",
            name="uq_invoice_source_reference",
        ),
        Index("ix_invoices_company_date", "company_id", "invoice_date"),
        Index("ix_invoices_company_gstin", "company_id", "gstin"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    vendor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("vendors.id", ondelete="SET NULL")
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    gstin: Mapped[str] = mapped_column(String(15), nullable=False)
    vendor_name: Mapped[Optional[str]] = mapped_column(String(255))
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    invoice_date: Mapped[Optional[date]] = mapped_column(Date)
    taxable_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    cgst: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    sgst: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    igst: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    company: Mapped["Company"] = relationship(back_populates="invoices")
    vendor: Mapped[Optional["Vendor"]] = relationship(back_populates="invoices")
    reconciliation_results: Mapped[list["ReconciliationResult"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class ReconciliationRun(Base):
    """Metadata and totals for one reconciliation execution."""

    __tablename__ = "reconciliation_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    total_books: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_gstr2b: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mismatch_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_in_gstr2b_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_in_books_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    company: Mapped["Company"] = relationship(back_populates="reconciliation_runs")
    results: Mapped[list["ReconciliationResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ReconciliationResult(Base):
    """The outcome of comparing one invoice across Books and GSTR-2B."""

    __tablename__ = "reconciliation_results"
    __table_args__ = (
        Index("ix_reconciliation_company_status", "company_id", "status"),
        Index("ix_reconciliation_run_id", "run_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    invoice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL")
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    match_tier: Mapped[Optional[str]] = mapped_column(String(80))
    taxable_value_difference: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    tax_difference: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    company: Mapped["Company"] = relationship(back_populates="reconciliation_results")
    run: Mapped["ReconciliationRun"] = relationship(back_populates="results")
    invoice: Mapped[Optional["Invoice"]] = relationship(
        back_populates="reconciliation_results"
    )


def create_database(database_url: str = DATABASE_URL):
    """Create all tables if they do not already exist and return the engine."""

    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    return engine


if __name__ == "__main__":
    create_database()
    print(f"Database created at: {DATABASE_PATH}")
