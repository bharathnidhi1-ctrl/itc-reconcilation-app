from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Date, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# ✅ THIS IS THE MISSING CLASS — vendor_risk.py imports it
class Vendor(Base):
    __tablename__ = "vendors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    gstin: Mapped[str] = mapped_column(String(15), nullable=False)
    vendor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    total_invoices: Mapped[int] = mapped_column(Integer, default=0)
    missing_invoices: Mapped[int] = mapped_column(Integer, default=0)
    blocked_itc: Mapped[float] = mapped_column(Float, default=0.0)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[str] = mapped_column(String(20), default="Low")
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    gstin: Mapped[str] = mapped_column(String(15), nullable=False)
    vendor_name: Mapped[str] = mapped_column(String(255), nullable=True)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    invoice_date: Mapped[datetime] = mapped_column(Date, nullable=True)
    taxable_value: Mapped[float] = mapped_column(Float, default=0.0)
    cgst: Mapped[float] = mapped_column(Float, default=0.0)
    sgst: Mapped[float] = mapped_column(Float, default=0.0)
    igst: Mapped[float] = mapped_column(Float, default=0.0)

class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    total_books: Mapped[int] = mapped_column(Integer, default=0)
    total_gstr2b: Mapped[int] = mapped_column(Integer, default=0)
    matched_count: Mapped[int] = mapped_column(Integer, default=0)
    mismatch_count: Mapped[int] = mapped_column(Integer, default=0)
    missing_in_gstr2b_count: Mapped[int] = mapped_column(Integer, default=0)
    missing_in_books_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ReconciliationResult(Base):
    __tablename__ = "reconciliation_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    invoice_id: Mapped[int] = mapped_column(Integer, ForeignKey("invoices.id"), nullable=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("reconciliation_runs.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    match_tier: Mapped[str] = mapped_column(String(100), nullable=True)
    taxable_value_difference: Mapped[float] = mapped_column(Float, default=0.0)
    tax_difference: Mapped[float] = mapped_column(Float, default=0.0)
    remarks: Mapped[str] = mapped_column(String(255), nullable=True)

def create_database():
    """In-memory SQLite — safe for Streamlit Cloud."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine
