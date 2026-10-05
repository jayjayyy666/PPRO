import os
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.application.dto.patient_dto import (
    DuplicateCheckResult,
    PatientCreateDTO,
    PatientResponseDTO,
    PatientUpdateDTO,
)
from src.application.services.patient_service import PatientService
from src.infrastructure.database import get_db, init_db
from src.infrastructure.repositories.patient_repository import PatientRepository
from src.infrastructure.seed import seed_database

# Inicializace FastAPI aplikace
app = FastAPI(
    title="Ordinace Na Vyhlídce – Ambulantní systém",
    description="Semestrální projekt PPRO (FIM UHK) – Zadání A: Rezervace v ordinaci (MUDr. Jana Hrubá)",
    version="0.1.0",
)

# Adresáře pro šablony a statické soubory
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def get_patient_service(db: Session = Depends(get_db)) -> PatientService:
    repository = PatientRepository(db)
    return PatientService(repository)


@app.on_event("startup")
def on_startup():
    """Automatická inicializace DB a seed syntetických dat při startu."""
    init_db()
    seed_database()


# ==========================================
# WEBOVÉ ROZHRANÍ PRO PANÍ VĚRU (UI)
# ==========================================

@app.get("/", include_in_schema=False)
def index_redirect():
    return RedirectResponse(url="/patients", status_code=status.HTTP_302_FOUND)


@app.get("/patients", response_class=HTMLResponse, include_in_schema=False)
def list_patients(
    request: Request,
    q: Optional[str] = None,
    msg: Optional[str] = None,
    service: PatientService = Depends(get_patient_service),
):
    """Zobrazení kartotéky pacientů s rychlým vyhledáváním dle příjmení či telefonu."""
    patients = service.search_patients(query=q or "", limit=100)
    return templates.TemplateResponse(
        "patients.html",
        {
            "request": request,
            "patients": patients,
            "query": q,
            "message": msg,
            "active_nav": "patients",
        },
    )


@app.get("/patients/new", response_class=HTMLResponse, include_in_schema=False)
def new_patient_form(request: Request):
    """Formulář pro zápis nového pacienta."""
    return templates.TemplateResponse(
        "patient_form.html",
        {
            "request": request,
            "form_data": {},
            "active_nav": "patients",
        },
    )


@app.post("/patients/new", response_class=HTMLResponse, include_in_schema=False)
def create_patient_web(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    birth_year: int = Form(...),
    phone: str = Form(...),
    insurance_id: str = Form(...),
    insurance_company_code: str = Form(...),
    note: Optional[str] = Form(None),
    confirm_duplicate: Optional[str] = Form(None),
    service: PatientService = Depends(get_patient_service),
):
    """Zpracování formuláře nového pacienta s kontrolou duplicity."""
    form_data = {
        "first_name": first_name,
        "last_name": last_name,
        "birth_year": birth_year,
        "phone": phone,
        "insurance_id": insurance_id,
        "insurance_company_code": insurance_company_code,
        "note": note,
    }

    # Kontrola duplicity (Otevřený bod 4 klienta)
    dup_check = service.check_duplicate(insurance_id=insurance_id, phone=phone)
    if dup_check.has_exact_match:
        return templates.TemplateResponse(
            "patient_form.html",
            {
                "request": request,
                "error": dup_check.message,
                "form_data": form_data,
                "existing_patient_id": dup_check.existing_patient.id if dup_check.existing_patient else None,
                "active_nav": "patients",
            },
            status_code=400,
        )

    try:
        dto = PatientCreateDTO(**form_data)
        new_patient = service.create_patient(dto)
        return RedirectResponse(
            url=f"/patients/{new_patient.id}?msg=Pacient+byl+uspesne+zaregistrovan",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as e:
        return templates.TemplateResponse(
            "patient_form.html",
            {
                "request": request,
                "error": str(e),
                "form_data": form_data,
                "active_nav": "patients",
            },
            status_code=400,
        )


@app.get("/patients/{patient_id}", response_class=HTMLResponse, include_in_schema=False)
def patient_detail(
    request: Request,
    patient_id: str,
    msg: Optional[str] = None,
    service: PatientService = Depends(get_patient_service),
):
    """Detail karty pojištěnce."""
    patient = service.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Pacient nebyl nalezen.")

    return templates.TemplateResponse(
        "patient_detail.html",
        {
            "request": request,
            "patient": patient,
            "message": msg,
            "active_nav": "patients",
        },
    )


@app.post("/patients/{patient_id}/delete", include_in_schema=False)
def delete_patient_web(
    patient_id: str,
    service: PatientService = Depends(get_patient_service),
):
    """Soft-delete pacienta (nikdy nemaže fyzicky historii)."""
    service.soft_delete_patient(patient_id)
    return RedirectResponse(
        url="/patients?msg=Pacient+byl+deaktivovan+(soft-delete)",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ==========================================
# REST API ENDPOINTY (PRO INTEGRACI & TESTY)
# ==========================================

@app.get(
    "/api/patients",
    response_model=List[PatientResponseDTO],
    tags=["Pacienti"],
    summary="Vyhledání pacientů (Fulltext/telefon/příjmení)",
)
def api_search_patients(
    q: Optional[str] = None,
    limit: int = 50,
    service: PatientService = Depends(get_patient_service),
):
    """Bleskové vyhledávání pacientů podle příjmení, jména nebo telefonního čísla."""
    return service.search_patients(query=q or "", limit=limit)


@app.post(
    "/api/patients",
    response_model=PatientResponseDTO,
    status_code=status.HTTP_201_CREATED,
    tags=["Pacienti"],
    summary="Vytvoření nového pacienta",
)
def api_create_patient(
    dto: PatientCreateDTO,
    service: PatientService = Depends(get_patient_service),
):
    """Založení nového pacienta s validací rodného čísla a telefonu."""
    try:
        return service.create_patient(dto)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get(
    "/api/patients/{patient_id}",
    response_model=PatientResponseDTO,
    tags=["Pacienti"],
    summary="Získání detailu pacienta",
)
def api_get_patient(
    patient_id: str,
    service: PatientService = Depends(get_patient_service),
):
    patient = service.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Pacient nebyl nalezen.")
    return patient


@app.post(
    "/api/patients/check-duplicate",
    response_model=DuplicateCheckResult,
    tags=["Pacienti"],
    summary="Kontrola duplicity pacienta",
)
def api_check_duplicate(
    insurance_id: str,
    phone: Optional[str] = None,
    service: PatientService = Depends(get_patient_service),
):
    """Ověření duplicity podle rodného čísla a telefonu (Otevřený bod 4 klienta)."""
    return service.check_duplicate(insurance_id=insurance_id, phone=phone)


@app.delete(
    "/api/patients/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Pacienti"],
    summary="Deaktivace pacienta (Soft-delete)",
)
def api_delete_patient(
    patient_id: str,
    service: PatientService = Depends(get_patient_service),
):
    """Měkké smazání pacienta bez narušení historie."""
    success = service.soft_delete_patient(patient_id)
    if not success:
        raise HTTPException(status_code=404, detail="Pacient nebyl nalezen.")
