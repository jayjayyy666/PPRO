from datetime import datetime
import uuid
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, Index
from src.infrastructure.database import Base


class PatientModel(Base):
    """
    SQLAlchemy model pro tabulku patients.
    Vynucuje:
    - Unikátnost pojištěnce (insurance_id) na úrovni DB.
    - Indexy pro rychlé vyhledávání příjmení a telefonu (pro okamžitou odezvu paní Věře).
    - Audit sloupce (created_at, updated_at).
    - Soft-delete: is_active a deleted_at (data se fyzicky nemažou).
    """
    __tablename__ = "patients"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False, index=True)
    birth_year = Column(Integer, nullable=False)
    phone = Column(String(30), nullable=False, index=True)
    insurance_id = Column(String(20), unique=True, nullable=False, index=True)
    insurance_company_code = Column(String(10), nullable=False)
    note = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_patients_search", "last_name", "phone"),
    )
