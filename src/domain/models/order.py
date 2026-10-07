"""
Doménový model pro zákazníky, objednávky a položky objednávek (Dřevěnka s.r.o.).
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional
import uuid


class OrderStatus(str, Enum):
    DRAFT = "DRAFT"  # Rozpracovaná objednávka
    CONFIRMED = "CONFIRMED"  # Potvrzená e-shopem, zásoby jsou atomicky zarezervovány
    PROCESSING = "PROCESSING"  # Připravuje se na skladě / balí se
    SHIPPED = "SHIPPED"  # Odeslána zákazníkovi, fyzicky odepsáno ze skladu
    CANCELLED = "CANCELLED"  # Stornována, rezervace byly uvolněny


class Customer:
    """
    Zákazník e-shopu.
    Pravidlo klienta: Zákazník se nemaže, protože se ke svým objednávkám vrací s reklamacemi.
    Používá se soft-delete (is_active).
    """

    def __init__(
        self,
        name: str,
        email: str,
        phone: str = "",
        address: str = "",
        is_active: bool = True,
        id: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ):
        if not name.strip():
            raise ValueError("Jméno zákazníka je povinné.")
        if not email.strip():
            raise ValueError("E-mail zákazníka je povinný.")

        self.id = id or str(uuid.uuid4())
        self.name = name.strip()
        self.email = email.strip().lower()
        self.phone = phone.strip()
        self.address = address.strip()
        self.is_active = is_active
        self.created_at = created_at or datetime.utcnow()

    def deactivate(self) -> None:
        """Soft-delete zákazníka bez fyzického smazání databáze."""
        self.is_active = False

    def __repr__(self) -> str:
        return f"<Customer(name='{self.name}', email='{self.email}')>"


class OrderItem:
    """
    Položka objednávky.
    Pravidlo klienta: Cena v odeslané objednávce se nesmí zpětně změnit, když se upraví ceník.
    Proto se 'unit_price' ukládá jako neměnný snapshot v okamžiku potvrzení objednávky.
    """

    def __init__(
        self,
        order_id: str,
        product_id: str,
        warehouse_id: str,
        quantity: int,
        unit_price: float,
        variant_id: Optional[str] = None,
        id: Optional[str] = None,
    ):
        if quantity <= 0:
            raise ValueError("Množství v položce objednávky musí být kladné.")
        if unit_price < 0:
            raise ValueError("Jednotková cena nesmí být záporná.")

        self.id = id or str(uuid.uuid4())
        self.order_id = order_id
        self.product_id = product_id
        self.variant_id = variant_id
        self.warehouse_id = warehouse_id
        self.quantity = int(quantity)
        self.unit_price = float(unit_price)

    @property
    def total_price(self) -> float:
        return self.quantity * self.unit_price

    def __repr__(self) -> str:
        return (
            f"<OrderItem(product_id={self.product_id}, qty={self.quantity}, "
            f"price={self.unit_price}, wh={self.warehouse_id})>"
        )


class Order:
    """
    Objednávka zákazníka.
    Obsahuje zákazníka, datum, stav, seznam položek a celkovou cenu.
    """

    def __init__(
        self,
        customer_id: str,
        order_number: str,
        status: OrderStatus = OrderStatus.CONFIRMED,
        items: Optional[List[OrderItem]] = None,
        note: str = "",
        id: Optional[str] = None,
        order_date: Optional[datetime] = None,
        shipped_at: Optional[datetime] = None,
    ):
        self.id = id or str(uuid.uuid4())
        self.customer_id = customer_id
        self.order_number = order_number.strip()
        self.status = status
        self.items = items or []
        self.note = note.strip()
        self.order_date = order_date or datetime.utcnow()
        self.shipped_at = shipped_at

    @property
    def total_price(self) -> float:
        return sum(item.total_price for item in self.items)

    def add_item(self, item: OrderItem) -> None:
        if self.status in [OrderStatus.SHIPPED, OrderStatus.CANCELLED]:
            raise ValueError("Do expedované nebo zrušené objednávky nelze přidávat položky.")
        self.items.append(item)

    def confirm(self) -> None:
        if self.status != OrderStatus.DRAFT:
            raise ValueError(f"Objednávku ve stavu {self.status} nelze znovu potvrdit.")
        self.status = OrderStatus.CONFIRMED

    def mark_shipped(self) -> None:
        if self.status == OrderStatus.CANCELLED:
            raise ValueError("Zrušenou objednávku nelze odeslat.")
        self.status = OrderStatus.SHIPPED
        self.shipped_at = datetime.utcnow()

    def cancel(self) -> None:
        if self.status == OrderStatus.SHIPPED:
            raise ValueError("Odeslanou objednávku již nelze stornovat (nutno řešit reklamací/vratkou).")
        self.status = OrderStatus.CANCELLED

    def __repr__(self) -> str:
        return f"<Order(number='{self.order_number}', status={self.status}, total={self.total_price})>"
