"""
Aplikační služba pro správu a odbavení objednávek.
Implementuje klíčové požadavky klienta:
  - Požadavek 4: Odmítnutí objednávky, na kterou nejsou zásoby („Důvod, proč se to celé dělá“).
  - Pravidlo klienta: Vydat víc, než je na skladě, nesmí jít.
  - Pravidlo klienta: Cena v objednávce se nesmí zpětně změnit při úpravě ceníku.
  - Otevřený bod 2: Dvoustavová evidence – rezervace při příjmu objednávky, fyzický odpis při expedici.
"""
from datetime import datetime
from typing import List, Optional
import uuid
from sqlalchemy.orm import Session

from src.domain.models import MovementType, OrderStatus
from src.infrastructure.models import (
    CustomerModel,
    OrderModel,
    OrderItemModel,
    ProductModel,
    StockItemModel,
    StockMovementModel,
    WarehouseModel,
)
from src.application.dto.inventory_dto import OrderCreateDTO, OrderResponseDTO, OrderItemResponseDTO


class OrderRejectionException(Exception):
    """Výjimka při zamítnutí objednávky z důvodu nedostatku zásob."""
    def __init__(self, message: str, missing_items: List[str]):
        super().__init__(message)
        self.missing_items = missing_items


class OrderService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_customer(self, name: str, email: str, phone: str = "", address: str = "") -> CustomerModel:
        customer = self.db.query(CustomerModel).filter(CustomerModel.email == email.strip().lower()).first()
        if not customer:
            customer = CustomerModel(
                name=name.strip(),
                email=email.strip().lower(),
                phone=phone.strip(),
                address=address.strip(),
                is_active=True,
            )
            self.db.add(customer)
            self.db.flush()
        else:
            # Aktualizace kontaktních údajů
            customer.name = name.strip()
            if phone:
                customer.phone = phone.strip()
            if address:
                customer.address = address.strip()
        return customer

    def create_order(self, data: OrderCreateDTO) -> OrderModel:
        """
        Vytvoření a atomické ověření objednávky.
        POKUD NEJSOU ZÁSOBY, OBJEDNÁVKA JE OKAMŽITĚ ODMÍTNUTA!
        """
        # 1. Zajištění zákazníka (zákazník se nemaže kvůli reklamacím)
        customer = self.get_or_create_customer(
            name=data.customer_name,
            email=data.customer_email,
            phone=data.customer_phone,
            address=data.customer_address,
        )

        # 2. Určení primárního skladu pro expedici (Centrální sklad Hradec Králové)
        primary_wh = self.db.query(WarehouseModel).filter(WarehouseModel.is_primary == True).first()
        if not primary_wh:
            primary_wh = self.db.query(WarehouseModel).first()

        missing_details = []
        validated_items = []

        # 3. Kontrola dostupnosti a cenový snapshot pro všechny položky
        for item_in in data.items:
            product = self.db.query(ProductModel).filter(ProductModel.id == item_in.product_id).first()
            if not product:
                missing_details.append(f"Produkt s ID {item_in.product_id} v databázi neexistuje.")
                continue

            wh_id = item_in.warehouse_id or primary_wh.id
            wh = self.db.query(WarehouseModel).filter(WarehouseModel.id == wh_id).first()

            # Pesimistický zámek řádku na skladě
            stock_item = (
                self.db.query(StockItemModel)
                .filter(
                    StockItemModel.warehouse_id == wh_id,
                    StockItemModel.product_id == product.id,
                )
                .with_for_update()
                .first()
            )

            available = (stock_item.physical_quantity - stock_item.reserved_quantity) if stock_item else 0
            if available < item_in.quantity:
                wh_name = wh.name if wh else "Sklad"
                missing_details.append(
                    f"Produkt '{product.name}' ({product.code}) na skladě '{wh_name}': "
                    f"požadováno {item_in.quantity} ks, ale volno je pouze {available} ks "
                    f"(fyzicky: {stock_item.physical_quantity if stock_item else 0}, rezervováno: {stock_item.reserved_quantity if stock_item else 0})."
                )
            else:
                validated_items.append((product, wh, stock_item, item_in.quantity))

        # POKUD COKOLIV CHYBÍ, CELÁ OBJEDNÁVKA JE ZAMÍTNUTA!
        if missing_details:
            self.db.rollback()
            raise OrderRejectionException(
                "Objednávka byla systémem zamítnuta: nedostatek skladových zásob pro požadované položky.",
                missing_items=missing_details,
            )

        # 4. Vše je skladem -> Vytvoření objednávky, snapshot cen a atomická rezervace zásob
        order_count = self.db.query(OrderModel).count() + 1
        year = datetime.utcnow().year
        order_num = f"OBJ-{year}-{order_count:04d}"

        order = OrderModel(
            customer_id=customer.id,
            order_number=order_num,
            status=OrderStatus.CONFIRMED,
            note=data.note,
            order_date=datetime.utcnow(),
            total_price=0.0,
        )
        self.db.add(order)
        self.db.flush()

        total_price = 0.0
        for product, wh, stock_item, qty in validated_items:
            unit_price = float(product.selling_price)  # CENOVÝ SNAPSHOT!
            total_price += unit_price * qty

            # Rezervace zásob (otevřený bod 2)
            stock_item.reserved_quantity += qty

            order_item = OrderItemModel(
                order_id=order.id,
                product_id=product.id,
                warehouse_id=wh.id,
                quantity=qty,
                unit_price=unit_price,
            )
            self.db.add(order_item)

        order.total_price = total_price
        self.db.commit()
        self.db.refresh(order)
        return order

    def ship_order(self, order_id: str, performed_by: str = "Petr Doležal") -> OrderModel:
        """
        Expedice a odeslání objednávky (fyzický odpis ze skladu a zápis výdejky).
        """
        order = self.db.query(OrderModel).filter(OrderModel.id == order_id).first()
        if not order:
            raise ValueError(f"Objednávka {order_id} neexistuje.")
        if order.status == OrderStatus.SHIPPED:
            raise ValueError("Objednávka již byla odeslána.")
        if order.status == OrderStatus.CANCELLED:
            raise ValueError("Zrušenou objednávku nelze odeslat.")

        for item in order.items:
            stock_item = (
                self.db.query(StockItemModel)
                .filter(
                    StockItemModel.warehouse_id == item.warehouse_id,
                    StockItemModel.product_id == item.product_id,
                )
                .with_for_update()
                .first()
            )
            if not stock_item or stock_item.physical_quantity < item.quantity:
                raise ValueError(
                    f"Kritická chyba expedice: Na skladě fyzicky chybí položka {item.product.name}."
                )

            # Fyzický odpis a uvolnění rezervace
            stock_item.physical_quantity -= item.quantity
            stock_item.reserved_quantity = max(0, stock_item.reserved_quantity - item.quantity)

            # Auditní záznam o výdeji (požadavek 5)
            movement = StockMovementModel(
                movement_type=MovementType.DISPATCH,
                product_id=item.product_id,
                quantity=item.quantity,
                source_warehouse_id=item.warehouse_id,
                reference_order_id=order.id,
                note=f"Výdej pro objednávku {order.order_number}",
                performed_by=performed_by,
            )
            self.db.add(movement)

        order.status = OrderStatus.SHIPPED
        order.shipped_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(order)
        return order

    def cancel_order(self, order_id: str) -> OrderModel:
        """
        Storno objednávky – uvolnění rezervovaných zásob.
        """
        order = self.db.query(OrderModel).filter(OrderModel.id == order_id).first()
        if not order:
            raise ValueError(f"Objednávka {order_id} neexistuje.")
        if order.status == OrderStatus.SHIPPED:
            raise ValueError("Odeslanou objednávku nelze stornovat (nutno řešit reklamací).")
        if order.status == OrderStatus.CANCELLED:
            return order

        # Uvolnění rezervací
        for item in order.items:
            stock_item = (
                self.db.query(StockItemModel)
                .filter(
                    StockItemModel.warehouse_id == item.warehouse_id,
                    StockItemModel.product_id == item.product_id,
                )
                .first()
            )
            if stock_item:
                stock_item.reserved_quantity = max(0, stock_item.reserved_quantity - item.quantity)

        order.status = OrderStatus.CANCELLED
        self.db.commit()
        self.db.refresh(order)
        return order

    def get_orders(self, limit: int = 50) -> List[OrderModel]:
        return self.db.query(OrderModel).order_by(OrderModel.order_date.desc()).limit(limit).all()

    def get_order_by_id(self, order_id: str) -> Optional[OrderModel]:
        return self.db.query(OrderModel).filter(OrderModel.id == order_id).first()
