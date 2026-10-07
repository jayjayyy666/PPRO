"""
Aplikační služba pro manažerské výkazy a alerting (Dřevěnka s.r.o.).
Implementuje:
  - Požadavek 7: Minimální zásoba a co doobjednat (Dashboard semafor: „Barevně, ať vidím, co hoří“).
  - Požadavek 8: Obrat po kategoriích za měsíc („Klient chce vědět, co ho živí“).
"""
from datetime import datetime
from typing import Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from src.infrastructure.models import (
    ProductModel,
    StockItemModel,
    CategoryModel,
    OrderModel,
    OrderItemModel,
    ProductCategoryModel,
)
from src.domain.models import OrderStatus
from src.application.dto.inventory_dto import LowStockAlertDTO, CategoryRevenueDTO


class ReportingService:
    def __init__(self, db: Session):
        self.db = db

    def get_low_stock_alerts(self) -> List[LowStockAlertDTO]:
        """
        Získá seznam produktů pro úvodní dashboard s barevným semaforem.
        ČERVENÁ: fyzický stav klesl POD minimum (hoří!).
        ŽLUTÁ: fyzický stav je těsně nad minimem (do 120 % minima).
        """
        products = self.db.query(ProductModel).all()
        alerts = []

        for prod in products:
            # Součet fyzických a disponibilních zásob napříč všemi sklady (Hradec + Garáž)
            total_physical = sum(s.physical_quantity for s in prod.stock_items)
            total_reserved = sum(s.reserved_quantity for s in prod.stock_items)
            total_available = max(0, total_physical - total_reserved)

            min_level = prod.min_stock_level

            if total_physical < min_level:
                status = "RED"  # Hoří!
            elif total_physical <= int(min_level * 1.2):
                status = "YELLOW"  # Pozor, blíží se minimum
            else:
                continue  # Zelené položky na výstražné tabuli nezobrazujeme

            # Doporučené množství k doobjednání / výrobě
            target_stock = max(min_level * 2, 10)
            recommended_reorder = max(0, target_stock - total_physical)

            alerts.append(
                LowStockAlertDTO(
                    product_id=prod.id,
                    product_code=prod.code,
                    product_name=prod.name,
                    current_physical_stock=total_physical,
                    current_available_stock=total_available,
                    min_stock_level=min_level,
                    recommended_reorder=recommended_reorder,
                    urgency_status=status,
                    categories=[c.name for c in prod.categories],
                )
            )

        # Seřadíme: nejdříve červené, potom podle nejnižšího stavu
        alerts.sort(key=lambda x: (0 if x.urgency_status == "RED" else 1, x.current_physical_stock))
        return alerts

    def get_monthly_category_revenue(self, year: int, month: int) -> List[CategoryRevenueDTO]:
        """
        Obrat po kategoriích za kalendářní měsíc (požadavek 8: „Klient chce vědět, co ho živí“).
        Počítá se z dokončených/odeslaných objednávek (nebo potvrzených v daném měsíci).
        """
        # Načteme všechny kategorie
        categories = self.db.query(CategoryModel).all()

        # Načteme položky objednávek pro daný měsíc a rok
        items_query = (
            self.db.query(
                OrderItemModel.product_id,
                OrderItemModel.quantity,
                OrderItemModel.unit_price,
                OrderModel.id.label("order_id"),
            )
            .join(OrderModel, OrderItemModel.order_id == OrderModel.id)
            .filter(
                OrderModel.status.in_([OrderStatus.CONFIRMED, OrderStatus.PROCESSING, OrderStatus.SHIPPED]),
                extract("year", OrderModel.order_date) == year,
                extract("month", OrderModel.order_date) == month,
            )
            .all()
        )

        # Mapa tržeb podle ID produktu
        product_stats: Dict[str, Dict] = {}
        for p_id, qty, unit_price, o_id in items_query:
            if p_id not in product_stats:
                product_stats[p_id] = {"quantity": 0, "revenue": 0.0, "orders": set()}
            product_stats[p_id]["quantity"] += qty
            product_stats[p_id]["revenue"] += qty * float(unit_price)
            product_stats[p_id]["orders"].add(o_id)

        # Přiřazení tržeb kategoriím (produkt může patřit do více kategorií současně - M:N)
        cat_results = []
        for cat in categories:
            cat_orders = set()
            cat_items = 0
            cat_revenue = 0.0

            for prod in cat.products:
                if prod.id in product_stats:
                    cat_orders.update(product_stats[prod.id]["orders"])
                    cat_items += product_stats[prod.id]["quantity"]
                    cat_revenue += product_stats[prod.id]["revenue"]

            cat_results.append(
                CategoryRevenueDTO(
                    category_id=cat.id,
                    category_name=cat.name,
                    total_orders_count=len(cat_orders),
                    total_items_sold=cat_items,
                    total_revenue=round(cat_revenue, 2),
                )
            )

        # Seřadíme sestupně podle tržeb
        cat_results.sort(key=lambda x: x.total_revenue, reverse=True)
        return cat_results
