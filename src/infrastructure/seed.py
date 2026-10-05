import sys
from src.infrastructure.database import SessionLocal, init_db
from src.infrastructure.repositories.patient_repository import PatientRepository
from src.domain.models.patient import Patient

# 100% syntetická anonymizovaná data pro předvedení klientovi a splnění minima
SYNTHETIC_PATIENTS = [
    {
        "first_name": "Alena",
        "last_name": "Krátká",
        "birth_year": 1974,
        "phone": "+420603112233",
        "insurance_id": "7458120011",
        "insurance_company_code": "111",
        "note": "Často ruší termíny na poslední chvíli. Pozor na plánování!",
    },
    {
        "first_name": "Marie",
        "last_name": "Nováková",
        "birth_year": 1958,
        "phone": "+420777123456",
        "insurance_id": "5860151234",
        "insurance_company_code": "111",
        "note": "Pravidelná kontrola krevního tlaku každé 3 měsíce.",
    },
    {
        "first_name": "Jan",
        "last_name": "Novák",
        "birth_year": 1982,
        "phone": "+420777123456",  # Stejný telefon jako manželka Marie Nováková pro test detekce duplicit
        "insurance_id": "8205105678",
        "insurance_company_code": "111",
        "note": "Manžel Marie Novákové, sdílené rodinné telefonní číslo.",
    },
    {
        "first_name": "Petr",
        "last_name": "Svoboda",
        "birth_year": 1990,
        "phone": "+420608998877",
        "insurance_id": "9011032345",
        "insurance_company_code": "205",
        "note": "Alergie na penicilin.",
    },
    {
        "first_name": "Eva",
        "last_name": "Dvořáková",
        "birth_year": 1965,
        "phone": "+420721445566",
        "insurance_id": "6554203456",
        "insurance_company_code": "207",
        "note": "Diabetička II. typu, sledována v dispenzáři.",
    },
    {
        "first_name": "Tomáš",
        "last_name": "Černý",
        "birth_year": 1995,
        "phone": "+420732889900",
        "insurance_id": "9507184567",
        "insurance_company_code": "211",
        "note": "Vstupní prohlídka do nového zaměstnání.",
    },
    {
        "first_name": "Jana",
        "last_name": "Procházková",
        "birth_year": 1988,
        "phone": "+420604556677",
        "insurance_id": "8859235678",
        "insurance_company_code": "111",
        "note": "Těhotenství - 2. trimestr.",
    },
    {
        "first_name": "Karel",
        "last_name": "Kučera",
        "birth_year": 1952,
        "phone": "+420775332211",
        "insurance_id": "5202146789",
        "insurance_company_code": "201",
        "note": "Kardiologický pacient, užívá Warfarin.",
    },
    {
        "first_name": "Lucie",
        "last_name": "Veselá",
        "birth_year": 2001,
        "phone": "+420739665544",
        "insurance_id": "0160257890",
        "insurance_company_code": "209",
        "note": "Studentka VŠ, prevence.",
    },
    {
        "first_name": "Jiří",
        "last_name": "Horák",
        "birth_year": 1978,
        "phone": "+420602987654",
        "insurance_id": "7809058901",
        "insurance_company_code": "111",
        "note": "Chronické bolesti zad po úrazu.",
    },
]


def seed_database():
    print("==> Inicializace databáze a seed syntetických dat...")
    init_db()
    db = SessionLocal()
    try:
        repo = PatientRepository(db)
        count = 0
        for data in SYNTHETIC_PATIENTS:
            existing = repo.get_by_insurance_id(data["insurance_id"])
            if not existing:
                p = Patient.create(
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    birth_year=data["birth_year"],
                    phone=data["phone"],
                    insurance_id=data["insurance_id"],
                    insurance_company_code=data["insurance_company_code"],
                    note=data.get("note"),
                )
                repo.save(p)
                count += 1
        print(f"==> Seed dokončen: Vloženo {count} nových syntetických pacientů (celkem v DB: {repo.count_active()}).")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
