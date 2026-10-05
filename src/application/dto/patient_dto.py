from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import re


class PatientCreateDTO(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=50, description="Křestní jméno")
    last_name: str = Field(..., min_length=2, max_length=50, description="Příjmení")
    birth_year: int = Field(..., ge=1900, le=2026, description="Rok narození")
    phone: str = Field(..., description="Telefonní číslo")
    insurance_id: str = Field(..., description="Identifikátor pojištěnce (rodné číslo bez lomítka)")
    insurance_company_code: str = Field(..., min_length=3, max_length=10, description="Kód pojišťovny (např. 111, 205)")
    note: Optional[str] = Field(None, max_length=500, description="Poznámka")

    @field_validator("phone")
    def validate_phone(cls, v: str) -> str:
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if not re.match(r"^\+?[0-9]{9,15}$", cleaned):
            raise ValueError("Telefonní číslo musí mít 9 až 15 číslic (např. +420777123456 nebo 777123456).")
        return cleaned

    @field_validator("insurance_id")
    def validate_insurance_id(cls, v: str) -> str:
        cleaned = re.sub(r"[\s/]", "", v)
        if not re.match(r"^[0-9]{9,10}$", cleaned):
            raise ValueError("Identifikátor pojištěnce / rodné číslo musí mít 9 nebo 10 číslic.")
        return cleaned


class PatientUpdateDTO(BaseModel):
    first_name: Optional[str] = Field(None, min_length=2, max_length=50)
    last_name: Optional[str] = Field(None, min_length=2, max_length=50)
    birth_year: Optional[int] = Field(None, ge=1900, le=2026)
    phone: Optional[str] = None
    insurance_company_code: Optional[str] = None
    note: Optional[str] = None


class PatientResponseDTO(BaseModel):
    id: str
    first_name: str
    last_name: str
    full_name: str
    birth_year: int
    phone: str
    insurance_id: str
    formatted_insurance_id: str
    insurance_company_code: str
    note: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None


class DuplicateCheckResult(BaseModel):
    has_exact_match: bool
    has_phone_match: bool
    existing_patient: Optional[PatientResponseDTO] = None
    message: Optional[str] = None
