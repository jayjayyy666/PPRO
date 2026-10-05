from datetime import datetime
from typing import List, Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session
from src.domain.models.patient import Patient
from src.infrastructure.models import PatientModel


class PatientRepository:
    def __init__(self, db: Session):
        self.db = db

    def _to_domain(self, model: PatientModel) -> Patient:
        return Patient(
            id=model.id,
            first_name=model.first_name,
            last_name=model.last_name,
            birth_year=model.birth_year,
            phone=model.phone,
            insurance_id=model.insurance_id,
            insurance_company_code=model.insurance_company_code,
            note=model.note,
            is_active=model.is_active,
            deleted_at=model.deleted_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def search(self, query: str = "", limit: int = 50) -> List[Patient]:
        """
        Vyhledání pacientů podle příjmení nebo telefonního čísla.
        Optimalizováno pro rychlé vyhledávání paní Věry během telefonátu.
        """
        q = self.db.query(PatientModel).filter(PatientModel.is_active.is_(True))
        if query:
            clean_q = query.strip()
            # Hledání v příjmení (i křestním jménu) i v telefonu
            pattern = f"%{clean_q}%"
            q = q.filter(
                or_(
                    PatientModel.last_name.ilike(pattern),
                    PatientModel.first_name.ilike(pattern),
                    PatientModel.phone.ilike(pattern),
                    PatientModel.insurance_id.ilike(pattern),
                )
            )
        models = q.order_by(PatientModel.last_name.asc(), PatientModel.first_name.asc()).limit(limit).all()
        return [self._to_domain(m) for m in models]

    def get_by_id(self, patient_id: str) -> Optional[Patient]:
        model = self.db.query(PatientModel).filter(PatientModel.id == patient_id).first()
        return self._to_domain(model) if model else None

    def get_by_insurance_id(self, insurance_id: str) -> Optional[Patient]:
        clean_id = Patient.clean_insurance_id(insurance_id)
        model = self.db.query(PatientModel).filter(PatientModel.insurance_id == clean_id).first()
        return self._to_domain(model) if model else None

    def get_by_phone(self, phone: str) -> List[Patient]:
        normalized = Patient.normalize_phone(phone)
        models = self.db.query(PatientModel).filter(
            PatientModel.phone == normalized,
            PatientModel.is_active.is_(True),
        ).all()
        return [self._to_domain(m) for m in models]

    def save(self, patient: Patient) -> Patient:
        existing = self.db.query(PatientModel).filter(PatientModel.id == patient.id).first()
        if existing:
            existing.first_name = patient.first_name
            existing.last_name = patient.last_name
            existing.birth_year = patient.birth_year
            existing.phone = patient.phone
            existing.insurance_id = patient.insurance_id
            existing.insurance_company_code = patient.insurance_company_code
            existing.note = patient.note
            existing.is_active = patient.is_active
            existing.deleted_at = patient.deleted_at
            existing.updated_at = datetime.utcnow()
        else:
            model = PatientModel(
                id=patient.id,
                first_name=patient.first_name,
                last_name=patient.last_name,
                birth_year=patient.birth_year,
                phone=patient.phone,
                insurance_id=patient.insurance_id,
                insurance_company_code=patient.insurance_company_code,
                note=patient.note,
                is_active=patient.is_active,
                deleted_at=patient.deleted_at,
                created_at=patient.created_at or datetime.utcnow(),
                updated_at=patient.updated_at or datetime.utcnow(),
            )
            self.db.add(model)
        self.db.commit()
        return self.get_by_id(patient.id)  # type: ignore

    def soft_delete(self, patient_id: str) -> bool:
        """
        Soft-delete: Záznam se nikdy fyzicky nemaže, pouze se označí jako neaktivní.
        """
        model = self.db.query(PatientModel).filter(PatientModel.id == patient_id).first()
        if not model:
            return False
        model.is_active = False
        model.deleted_at = datetime.utcnow()
        self.db.commit()
        return True

    def count_active(self) -> int:
        return self.db.query(PatientModel).filter(PatientModel.is_active.is_(True)).count()
