import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.application.dto.patient_dto import PatientCreateDTO
from src.application.services.patient_service import PatientService
from src.domain.models.patient import Patient
from src.infrastructure.database import Base
from src.infrastructure.repositories.patient_repository import PatientRepository


@pytest.fixture
def db_session():
    """In-memory SQLite session pro rychlé a izolované testování."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def patient_service(db_session):
    repo = PatientRepository(db_session)
    return PatientService(repo)


def test_create_patient_success(patient_service):
    """Ověření úspěšného založení pacienta s normalizací telefonu a rodného čísla."""
    dto = PatientCreateDTO(
        first_name="Marie",
        last_name="Nováková",
        birth_year=1980,
        phone=" 777 123 456 ",
        insurance_id="805512/1234",
        insurance_company_code="111",
        note="Pravidelná kontrola",
    )

    created = patient_service.create_patient(dto)

    assert created.id is not None
    assert created.first_name == "Marie"
    assert created.last_name == "Nováková"
    assert created.full_name == "Marie Nováková"
    assert created.phone == "+420777123456"
    assert created.insurance_id == "8055121234"
    assert created.formatted_insurance_id == "805512/1234"
    assert created.is_active is True


def test_duplicate_insurance_id_rejected(patient_service):
    """
    Otevřený bod 4 klienta: Zákaz vytvoření duplikátu s totožným rodným číslem / pojištěncem.
    """
    dto1 = PatientCreateDTO(
        first_name="Petr",
        last_name="Novák",
        birth_year=1975,
        phone="602111222",
        insurance_id="7503151234",
        insurance_company_code="111",
    )
    patient_service.create_patient(dto1)

    # Pokus o vložení pacienta se stejným rodným číslem (např. se zadaným lomítkem)
    dto2 = PatientCreateDTO(
        first_name="Petr",
        last_name="Novák Duplicitní",
        birth_year=1975,
        phone="602999888",
        insurance_id="750315/1234",
        insurance_company_code="111",
    )

    with pytest.raises(ValueError, match="již v systému existuje"):
        patient_service.create_patient(dto2)


def test_duplicate_check_by_phone(patient_service):
    """
    Ověření varování před shodou telefonu (např. 'paní Nováková je třikrát').
    """
    dto = PatientCreateDTO(
        first_name="Eva",
        last_name="Dvořáková",
        birth_year=1990,
        phone="+420721445566",
        insurance_id="9051011111",
        insurance_company_code="205",
    )
    patient_service.create_patient(dto)

    # Kontrola duplicity se stejným telefonem, ale jiným RČ
    check = patient_service.check_duplicate(
        insurance_id="9502022222",
        phone="721 445 566",
    )

    assert check.has_exact_match is False
    assert check.has_phone_match is True
    assert "Eva Dvořáková" in check.message


def test_search_by_name_and_phone(patient_service):
    """
    Klíčová funkce pro paní Věru: Rychlé vyhledání podle části příjmení i části telefonu.
    """
    p1 = PatientCreateDTO(
        first_name="Karel",
        last_name="Kučera",
        birth_year=1960,
        phone="+420775332211",
        insurance_id="6001011234",
        insurance_company_code="201",
    )
    p2 = PatientCreateDTO(
        first_name="Alena",
        last_name="Krátká",
        birth_year=1974,
        phone="+420603112233",
        insurance_id="7458120011",
        insurance_company_code="111",
    )
    patient_service.create_patient(p1)
    patient_service.create_patient(p2)

    # Hledání dle příjmení
    results_name = patient_service.search_patients("Kučer")
    assert len(results_name) == 1
    assert results_name[0].last_name == "Kučera"

    # Hledání dle telefonu
    results_phone = patient_service.search_patients("603112")
    assert len(results_phone) == 1
    assert results_phone[0].last_name == "Krátká"


def test_soft_delete_preserves_history(patient_service, db_session):
    """
    Nekompromisní pravidlo klienta: 'Historie pacienta se nemaže. Když se něco stane,
    musím doložit, co jsme kdy dělali.'
    """
    from src.infrastructure.models import PatientModel

    dto = PatientCreateDTO(
        first_name="Jiří",
        last_name="Horák",
        birth_year=1985,
        phone="+420608000111",
        insurance_id="8505051234",
        insurance_company_code="207",
    )
    created = patient_service.create_patient(dto)

    # Provedeme deaktivaci (soft-delete)
    deleted = patient_service.soft_delete_patient(created.id)
    assert deleted is True

    # Z aktivní kartotéky (pro vyhledávání paní Věry) zmizel
    search_results = patient_service.search_patients("Horák")
    assert len(search_results) == 0

    # V databázi však záznam fyzicky ZŮSTAL se statusem is_active=False a vyplněným deleted_at
    raw_record = db_session.query(PatientModel).filter(PatientModel.id == created.id).first()
    assert raw_record is not None
    assert raw_record.is_active is False
    assert raw_record.deleted_at is not None
