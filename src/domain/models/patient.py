import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class Patient:
    """
    Doménová entita Pacienta reprezentující záznam v kartotéce ordinace.
    Odpovídá požadavkům klienta:
    - Jméno, příjmení, rok narození, telefon, identifikátor pojištěnce (rodné číslo), pojišťovna.
    - Soft-delete: historie pacienta se nikdy fyzicky nemaže.
    """
    id: str
    first_name: str
    last_name: str
    birth_year: int
    phone: str
    insurance_id: str
    insurance_company_code: str
    note: Optional[str] = None
    is_active: bool = True
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        first_name: str,
        last_name: str,
        birth_year: int,
        phone: str,
        insurance_id: str,
        insurance_company_code: str,
        note: Optional[str] = None,
    ) -> "Patient":
        normalized_phone = cls.normalize_phone(phone)
        clean_insurance_id = cls.clean_insurance_id(insurance_id)

        cls.validate_data(
            first_name=first_name,
            last_name=last_name,
            birth_year=birth_year,
            phone=normalized_phone,
            insurance_id=clean_insurance_id,
            insurance_company_code=insurance_company_code,
        )

        return cls(
            id=str(uuid.uuid4()),
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            birth_year=birth_year,
            phone=normalized_phone,
            insurance_id=clean_insurance_id,
            insurance_company_code=insurance_company_code.strip(),
            note=note.strip() if note else None,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Odstraní mezery, pomlčky a zajistí mezinárodní předvolbu +420 pokud chybí."""
        cleaned = re.sub(r"[\s\-\(\)]", "", phone.strip())
        if cleaned.startswith("00420"):
            cleaned = "+420" + cleaned[5:]
        elif not cleaned.startswith("+"):
            if len(cleaned) == 9:
                cleaned = "+420" + cleaned
        return cleaned

    @staticmethod
    def clean_insurance_id(insurance_id: str) -> str:
        """Vyčistí rodné číslo od lomítek a mezer."""
        return re.sub(r"[\s/]", "", insurance_id.strip())

    @staticmethod
    def validate_data(
        first_name: str,
        last_name: str,
        birth_year: int,
        phone: str,
        insurance_id: str,
        insurance_company_code: str,
    ) -> None:
        if not first_name or len(first_name.strip()) < 2:
            raise ValueError("Křestní jméno musí mít alespoň 2 znaky.")
        if not last_name or len(last_name.strip()) < 2:
            raise ValueError("Příjmení musí mít alespoň 2 znaky.")

        current_year = datetime.utcnow().year
        if birth_year < 1900 or birth_year > current_year:
            raise ValueError(f"Rok narození musí být mezi 1900 a {current_year}.")

        if not re.match(r"^\+?[0-9]{9,15}$", phone):
            raise ValueError("Neplatný formát telefonního čísla.")

        if not re.match(r"^[0-9]{9,10}$", insurance_id):
            raise ValueError("Identifikátor pojištěnce (rodné číslo) musí mít 9 nebo 10 číslic.")

        if not insurance_company_code or len(insurance_company_code.strip()) < 3:
            raise ValueError("Kód pojišťovny musí být třímístný kód (např. 111, 205).")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def formatted_insurance_id(self) -> str:
        """Formátuje rodné číslo s lomítkem (pro přehlednost paní Věry: 850101/1234)."""
        if len(self.insurance_id) == 10:
            return f"{self.insurance_id[:6]}/{self.insurance_id[6:]}"
        elif len(self.insurance_id) == 9:
            return f"{self.insurance_id[:6]}/{self.insurance_id[6:]}"
        return self.insurance_id
