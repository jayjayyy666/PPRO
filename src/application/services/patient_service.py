from typing import List, Optional
from src.application.dto.patient_dto import (
    DuplicateCheckResult,
    PatientCreateDTO,
    PatientResponseDTO,
    PatientUpdateDTO,
)
from src.domain.models.patient import Patient
from src.infrastructure.repositories.patient_repository import PatientRepository


class PatientService:
    """
    Aplikační služba zapouzdřující byznys logiku pro správu pacientů.
    Dodržuje striktní pravidla:
    - Zákaz duplikace pojištěnce (rodného čísla).
    - Varování před shodou telefonního čísla (detekce duplicit à la 'paní Nováková je třikrát').
    - Nemazání historie (pouze soft-delete).
    """

    def __init__(self, repository: PatientRepository):
        self.repository = repository

    def _to_response_dto(self, patient: Patient) -> PatientResponseDTO:
        return PatientResponseDTO(
            id=patient.id,
            first_name=patient.first_name,
            last_name=patient.last_name,
            full_name=patient.full_name,
            birth_year=patient.birth_year,
            phone=patient.phone,
            insurance_id=patient.insurance_id,
            formatted_insurance_id=patient.formatted_insurance_id,
            insurance_company_code=patient.insurance_company_code,
            note=patient.note,
            is_active=patient.is_active,
            created_at=patient.created_at,
        )

    def search_patients(self, query: str = "", limit: int = 50) -> List[PatientResponseDTO]:
        patients = self.repository.search(query=query, limit=limit)
        return [self._to_response_dto(p) for p in patients]

    def get_patient(self, patient_id: str) -> Optional[PatientResponseDTO]:
        patient = self.repository.get_by_id(patient_id)
        return self._to_response_dto(patient) if patient else None

    def check_duplicate(self, insurance_id: str, phone: Optional[str] = None) -> DuplicateCheckResult:
        """
        Ověří, zda pacient s daným rodným číslem nebo telefonem již v kartotéce neexistuje.
        Řeší Otevřený bod 4 klienta (detekce duplicit před uložením).
        """
        clean_insurance = Patient.clean_insurance_id(insurance_id)
        existing_by_ins = self.repository.get_by_insurance_id(clean_insurance)

        if existing_by_ins:
            return DuplicateCheckResult(
                has_exact_match=True,
                has_phone_match=False,
                existing_patient=self._to_response_dto(existing_by_ins),
                message=f"Pacient s rodným číslem {existing_by_ins.formatted_insurance_id} již v kartotéce existuje ({existing_by_ins.full_name}).",
            )

        if phone:
            norm_phone = Patient.normalize_phone(phone)
            by_phone = self.repository.get_by_phone(norm_phone)
            if by_phone:
                first = by_phone[0]
                return DuplicateCheckResult(
                    has_exact_match=False,
                    has_phone_match=True,
                    existing_patient=self._to_response_dto(first),
                    message=f"Telefon {norm_phone} je již registrován u pacienta: {first.full_name} ({first.formatted_insurance_id}). Může jít o duplicitu nebo rodinného příslušníka.",
                )

        return DuplicateCheckResult(has_exact_match=False, has_phone_match=False)

    def create_patient(self, dto: PatientCreateDTO) -> PatientResponseDTO:
        clean_insurance = Patient.clean_insurance_id(dto.insurance_id)

        # Kontrola unikátnosti rodného čísla
        existing = self.repository.get_by_insurance_id(clean_insurance)
        if existing:
            raise ValueError(
                f"Pacient s tímto rodným číslem již v systému existuje ({existing.full_name}, nar. {existing.birth_year}). Duplicitu nelze vytvořit."
            )

        patient = Patient.create(
            first_name=dto.first_name,
            last_name=dto.last_name,
            birth_year=dto.birth_year,
            phone=dto.phone,
            insurance_id=clean_insurance,
            insurance_company_code=dto.insurance_company_code,
            note=dto.note,
        )

        saved = self.repository.save(patient)
        return self._to_response_dto(saved)

    def update_patient(self, patient_id: str, dto: PatientUpdateDTO) -> PatientResponseDTO:
        patient = self.repository.get_by_id(patient_id)
        if not patient:
            raise ValueError(f"Pacient s ID {patient_id} nebyl nalezen.")

        if dto.first_name is not None:
            patient.first_name = dto.first_name.strip()
        if dto.last_name is not None:
            patient.last_name = dto.last_name.strip()
        if dto.birth_year is not None:
            patient.birth_year = dto.birth_year
        if dto.phone is not None:
            patient.phone = Patient.normalize_phone(dto.phone)
        if dto.insurance_company_code is not None:
            patient.insurance_company_code = dto.insurance_company_code.strip()
        if dto.note is not None:
            patient.note = dto.note.strip() if dto.note else None

        saved = self.repository.save(patient)
        return self._to_response_dto(saved)

    def soft_delete_patient(self, patient_id: str) -> bool:
        """
        Měkké smazání: pacient je deaktivován, ale jeho historie zůstává zachována.
        """
        return self.repository.soft_delete(patient_id)
