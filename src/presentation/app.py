"""
FastAPI webová aplikace a REST API pro Dřevěnka s.r.o.
Prezentační vrstva třívrstvé architektury.
"""
from datetime import datetime
import os
from typing import List, Optional
from fastapi import FastAPI, Depends, Request, Form, Query, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.infrastructure.database import get_db, init_db
from src.infrastructure.models import (
    ProductModel,
    CategoryModel,
    WarehouseModel,
    StockItemModel,
    OrderModel,
)
from src.application.services.inventory_service import (
    InventoryService,
    InsufficientStockException,
)
from src.application.services.order_service import (
    OrderService,
    OrderRejectionException,
)
from src.application.services.reporting_service import ReportingService
from src.application.dto.inventory_dto import (
    ProductCreateDTO,
    ProductResponseDTO,
    OrderCreateDTO,
    OrderResponseDTO,
    StockTransferDTO,
    InventoryAdjustmentDTO,
    LowStockAlertDTO,
    CategoryRevenueDTO,
)
from src.infrastructure.seed import seed_database

# Inicializace tabulek v databázi
init_db()

# Automatický seed při startu (pokud je prázdno)
try:
    seed_database()
except Exception as e:
    print(f"Seed info: {e}")

app = FastAPI(
    title="Dřevěnka s.r.o. – Skladový systém",
    description="Skladový a expediční systém pro e-shop dřevěných hraček (Petr Doležal). Semestrální projekt PPRO FIM UHK.",
    version="1.0.0",
)

# Statické soubory a šablony Jinja2
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)


# ============================================================================
# WEBOVÉ ROZHRANÍ (JINJA2 ŠABLONY)
# ============================================================================

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def page_dashboard(request: Request, db: Session = Depends(get_db)):
    """Hlavní dashboard s barevným semaforem ('Co hoří')."""
    rep_service = ReportingService(db)
    inv_service = InventoryService(db)

    low_stock_alerts = rep_service.get_low_stock_alerts()
    warehouses = inv_service.get_warehouses()

    total_prods = db.query(ProductModel).count()

    # Spočítáme stavy v Hradci a v Garáži
    wh_h = next((w for w in warehouses if w.code == "HRADEC"), None)
    wh_g = next((w for w in warehouses if w.code == "TREBECHOVICE"), None)

    h_stock = (
        db.query(StockItemModel)
        .filter(StockItemModel.warehouse_id == wh_h.id)
        .all()
        if wh_h
        else []
    )
    g_stock = (
        db.query(StockItemModel)
        .filter(StockItemModel.warehouse_id == wh_g.id)
        .all()
        if wh_g
        else []
    )

    h_total = sum(s.physical_quantity for s in h_stock)
    g_total = sum(s.physical_quantity for s in g_stock)

    red_count = sum(1 for a in low_stock_alerts if a.urgency_status == "RED")

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "active_page": "dashboard",
            "total_products_count": total_prods,
            "hradec_total_stock": h_total,
            "garaz_total_stock": g_total,
            "red_alerts_count": red_count,
            "low_stock_alerts": low_stock_alerts,
        },
    )


@app.get("/products", response_class=HTMLResponse)
def page_products(
    request: Request,
    q: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Katalog dřevěných hraček s rozpadem zásob po skladech."""
    query_obj = db.query(ProductModel)

    if q:
        query_obj = query_obj.filter(
            (ProductModel.name.ilike(f"%{q}%")) | (ProductModel.code.ilike(f"%{q}%"))
        )

    if category:
        query_obj = query_obj.filter(ProductModel.categories.any(CategoryModel.id == category))

    products = query_obj.order_by(ProductModel.code).all()
    categories = db.query(CategoryModel).order_by(CategoryModel.name).all()

    return templates.TemplateResponse(
        "products.html",
        {
            "request": request,
            "active_page": "products",
            "products": products,
            "categories": categories,
            "query": q,
            "selected_category": category,
        },
    )


@app.get("/orders", response_class=HTMLResponse)
def page_orders(
    request: Request,
    error: Optional[str] = None,
    success: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Správa objednávek a zadání nové objednávky."""
    order_service = OrderService(db)
    inv_service = InventoryService(db)

    orders = order_service.get_orders(limit=100)
    products = db.query(ProductModel).order_by(ProductModel.name).all()
    warehouses = inv_service.get_warehouses()

    return templates.TemplateResponse(
        "orders.html",
        {
            "request": request,
            "active_page": "orders",
            "orders": orders,
            "available_products": products,
            "warehouses": warehouses,
            "error": error,
            "success": success,
        },
    )


@app.post("/orders/new")
def handle_create_order(
    request: Request,
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    customer_phone: str = Form(""),
    product_id: str = Form(...),
    quantity: int = Form(...),
    warehouse_id: Optional[str] = Form(None),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    """Zpracování nové objednávky s přísnou kontrolou a odmítnutím při nedostatku."""
    order_service = OrderService(db)
    from src.application.dto.inventory_dto import OrderItemCreateDTO

    order_in = OrderCreateDTO(
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        items=[OrderItemCreateDTO(product_id=product_id, quantity=quantity, warehouse_id=warehouse_id)],
        note=note,
    )

    try:
        order = order_service.create_order(order_in)
        return RedirectResponse(
            url=f"/orders?success=Objednávka {order.order_number} byla úspěšně přijata a zásoby zarezervovány.",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except OrderRejectionException as ex:
        # KLÍČOVÉ: Požadavek 4 - Odmítnutí objednávky!
        err_msg = f"{str(ex)} Detaily: {'; '.join(ex.missing_items)}"
        return RedirectResponse(
            url=f"/orders?error={err_msg}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as ex:
        return RedirectResponse(
            url=f"/orders?error=Chyba: {str(ex)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@app.post("/orders/{order_id}/ship")
def handle_ship_order(order_id: str, db: Session = Depends(get_db)):
    order_service = OrderService(db)
    try:
        order = order_service.ship_order(order_id)
        return RedirectResponse(
            url=f"/orders?success=Objednávka {order.order_number} byla expedována a odepsána ze skladu.",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as ex:
        return RedirectResponse(
            url=f"/orders?error=Chyba expedice: {str(ex)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@app.post("/orders/{order_id}/cancel")
def handle_cancel_order(order_id: str, db: Session = Depends(get_db)):
    order_service = OrderService(db)
    try:
        order = order_service.cancel_order(order_id)
        return RedirectResponse(
            url=f"/orders?success=Objednávka {order.order_number} byla stornována a rezervace uvolněny.",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as ex:
        return RedirectResponse(
            url=f"/orders?error=Chyba storna: {str(ex)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@app.get("/transfer", response_class=HTMLResponse)
def page_transfer(
    request: Request,
    product_id: Optional[str] = None,
    error: Optional[str] = None,
    success: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Formulář meziskladového převodu."""
    inv_service = InventoryService(db)
    products = db.query(ProductModel).order_by(ProductModel.name).all()
    warehouses = inv_service.get_warehouses()

    return templates.TemplateResponse(
        "transfer.html",
        {
            "request": request,
            "active_page": "transfer",
            "products": products,
            "warehouses": warehouses,
            "selected_product_id": product_id,
            "error": error,
            "success": success,
        },
    )


@app.post("/transfer")
def handle_transfer(
    product_id: str = Form(...),
    from_warehouse_id: str = Form(...),
    to_warehouse_id: str = Form(...),
    quantity: int = Form(...),
    note: str = Form(""),
    performed_by: str = Form("Petr Doležal"),
    db: Session = Depends(get_db),
):
    """Zpracování převodu mezi sklady."""
    inv_service = InventoryService(db)
    try:
        inv_service.transfer_stock(
            product_id=product_id,
            from_warehouse_id=from_warehouse_id,
            to_warehouse_id=to_warehouse_id,
            quantity=quantity,
            note=note,
            performed_by=performed_by,
        )
        return RedirectResponse(
            url="/movements?success=Meziskladový přesun byl úspěšně zaevidován a proveden.",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except InsufficientStockException as ex:
        return RedirectResponse(
            url=f"/transfer?product_id={product_id}&error={str(ex)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as ex:
        return RedirectResponse(
            url=f"/transfer?product_id={product_id}&error=Chyba: {str(ex)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@app.get("/movements", response_class=HTMLResponse)
def page_movements(
    request: Request,
    success: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Auditní log pohybů pro dohledání (požadavek 5)."""
    inv_service = InventoryService(db)
    movements = inv_service.get_movements_history(limit=100)

    return templates.TemplateResponse(
        "movements.html",
        {
            "request": request,
            "active_page": "movements",
            "movements": movements,
            "success": success,
        },
    )


@app.get("/reports", response_class=HTMLResponse)
def page_reports(
    request: Request,
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Měsíční obrat po kategoriích (požadavek 8: Co firmu živí)."""
    now = datetime.utcnow()
    y = year or now.year
    m = month or now.month

    rep_service = ReportingService(db)
    cat_stats = rep_service.get_monthly_category_revenue(year=y, month=m)
    total_rev = sum(c.total_revenue for c in cat_stats)

    return templates.TemplateResponse(
        "reports.html",
        {
            "request": request,
            "active_page": "reports",
            "selected_year": y,
            "selected_month": m,
            "category_stats": cat_stats,
            "total_revenue": total_rev,
        },
    )


# ============================================================================
# REST API ENDPOINTY (PRO INTEGRACI S E-SHOPEM)
# ============================================================================

@app.get("/api/products", response_model=List[ProductResponseDTO], tags=["Products"])
def api_get_products(db: Session = Depends(get_db)):
    products = db.query(ProductModel).all()
    results = []
    for p in products:
        phys = sum(s.physical_quantity for s in p.stock_items)
        res = sum(s.reserved_quantity for s in p.stock_items)
        avail = max(0, phys - res)
        stock_details = [
            {
                "warehouse_id": s.warehouse_id,
                "warehouse_name": s.warehouse.name,
                "warehouse_code": s.warehouse.code,
                "physical_quantity": s.physical_quantity,
                "reserved_quantity": s.reserved_quantity,
                "available_quantity": s.physical_quantity - s.reserved_quantity,
            }
            for s in p.stock_items
        ]
        results.append(
            ProductResponseDTO(
                id=p.id,
                code=p.code,
                name=p.name,
                purchase_price=p.purchase_price,
                selling_price=p.selling_price,
                description=p.description,
                min_stock_level=p.min_stock_level,
                total_physical_stock=phys,
                total_reserved_stock=res,
                total_available_stock=avail,
                is_below_minimum=phys < p.min_stock_level,
                categories=[{"id": c.id, "name": c.name, "description": c.description} for c in p.categories],
                stock_details=stock_details,
            )
        )
    return results


@app.post("/api/orders", response_model=OrderResponseDTO, status_code=status.HTTP_201_CREATED, tags=["Orders"])
def api_create_order(data: OrderCreateDTO, db: Session = Depends(get_db)):
    """Vytvoření objednávky z e-shopu s atomickou kontrolou a rezervací."""
    order_service = OrderService(db)
    try:
        order = order_service.create_order(data)
        return OrderResponseDTO(
            id=order.id,
            order_number=order.order_number,
            customer_name=order.customer.name,
            customer_email=order.customer.email,
            status=order.status,
            total_price=order.total_price,
            note=order.note,
            order_date=order.order_date,
            items=[
                {
                    "id": i.id,
                    "product_id": i.product_id,
                    "product_code": i.product.code,
                    "product_name": i.product.name,
                    "warehouse_id": i.warehouse_id,
                    "warehouse_name": i.warehouse.name,
                    "quantity": i.quantity,
                    "unit_price": i.unit_price,
                    "total_price": i.quantity * i.unit_price,
                }
                for i in order.items
            ],
        )
    except OrderRejectionException as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(ex), "missing_items": ex.missing_items},
        )


@app.post("/api/transfer", tags=["Inventory"])
def api_transfer_stock(data: StockTransferDTO, db: Session = Depends(get_db)):
    inv_service = InventoryService(db)
    try:
        inv_service.transfer_stock(
            product_id=data.product_id,
            from_warehouse_id=data.from_warehouse_id,
            to_warehouse_id=data.to_warehouse_id,
            quantity=data.quantity,
            note=data.note,
            performed_by=data.performed_by,
        )
        return {"status": "success", "message": "Převod byl úspěšně proveden."}
    except InsufficientStockException as ex:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ex))


@app.get("/api/reports/low-stock", response_model=List[LowStockAlertDTO], tags=["Reports"])
def api_low_stock_alerts(db: Session = Depends(get_db)):
    rep_service = ReportingService(db)
    return rep_service.get_low_stock_alerts()


@app.get("/api/reports/category-revenue", response_model=List[CategoryRevenueDTO], tags=["Reports"])
def api_category_revenue(
    year: int = Query(default=2026),
    month: int = Query(default=10),
    db: Session = Depends(get_db),
):
    rep_service = ReportingService(db)
    return rep_service.get_monthly_category_revenue(year=year, month=month)
