"""
Doménový model pro sklady, zásoby a auditní pohyby (Dřevěnka s.r.o.).
"""
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


class MovementType(str, Enum):
    RECEIPT = "RECEIPT"  # Naskladnění od dodavatele / z výroby
    DISPATCH = "DISPATCH"  # Vyskladnění zákazníkovi (odeslání objednávky)
    TRANSFER_OUT = "TRANSFER_OUT"  # Výdej v rámci meziskladového převodu
    TRANSFER_IN = "TRANSFER_IN"  # Příjem v rámci meziskladového převodu
    INVENTORY_ADJUSTMENT = "INVENTORY_ADJUSTMENT"  # Úprava inventurou (manko/přebytek)


class Warehouse:
    """
    Sklad firmy (např. Centrální sklad Hradec Králové, Garáž Třebechovice).
    """

    def __init__(
        self,
        code: str,
        name: str,
        address: str = "",
        is_primary: bool = False,
        id: Optional[str] = None,
    ):
        self.id = id or str(uuid.uuid4())
        self.code = code.strip().upper()
        self.name = name.strip()
        self.address = address.strip()
        self.is_primary = is_primary

    def __repr__(self) -> str:
        return f"<Warehouse(code='{self.code}', name='{self.name}')>"


class StockItem:
    """
    Skladová karta pro konkrétní produkt/variantu na konkrétním skladě.
    Implementuje dvoustavovou evidenci zásob (otevřený bod 2):
      - physical_quantity: reálný fyzický stav na polici (musí být >= 0, zákaz záporného stavu - bod 3)
      - reserved_quantity: zásoba blokovaná rozpracovanými objednávkami
      - available_quantity: volná disponibilní zásoba pro nový prodej (physical - reserved)
    """

    def __init__(
        self,
        warehouse_id: str,
        product_id: str,
        physical_quantity: int = 0,
        reserved_quantity: int = 0,
        variant_id: Optional[str] = None,
        id: Optional[str] = None,
    ):
        if physical_quantity < 0:
            raise ValueError("Fyzický stav zásob nesmí být záporný (zákaz záporného stavu dle bodu 3).")
        if reserved_quantity < 0:
            raise ValueError("Rezervované množství nesmí být záporné.")

        self.id = id or str(uuid.uuid4())
        self.warehouse_id = warehouse_id
        self.product_id = product_id
        self.variant_id = variant_id
        self.physical_quantity = int(physical_quantity)
        self.reserved_quantity = int(reserved_quantity)

    @property
    def available_quantity(self) -> int:
        """Disponibilní zásoba (kolik kusů lze ještě nabídnout k prodeji)."""
        return max(0, self.physical_quantity - self.reserved_quantity)

    def reserve(self, count: int) -> None:
        """Rezervace zboží pro novou objednávku."""
        if count <= 0:
            raise ValueError("Rezervované množství musí být kladné číslo.")
        if self.available_quantity < count:
            raise ValueError(
                f"Nedostatek disponibilních zásob pro rezervaci. "
                f"Požadováno: {count}, volno: {self.available_quantity} (fyzicky: {self.physical_quantity}, rezervováno: {self.reserved_quantity})."
            )
        self.reserved_quantity += count

    def release_reservation(self, count: int) -> None:
        """Uvolnění rezervace (např. při stornu objednávky)."""
        if count <= 0:
            raise ValueError("Uvolňované množství musí být kladné číslo.")
        self.reserved_quantity = max(0, self.reserved_quantity - count)

    def dispatch(self, count: int) -> None:
        """Fyzický odpis zboží při odeslání expedicí."""
        if count <= 0:
            raise ValueError("Vyskladňované množství musí být kladné číslo.")
        if self.physical_quantity < count:
            raise ValueError(
                f"Nelze vydat víc, než je fyzicky na skladě. "
                f"Fyzicky na skladě: {self.physical_quantity}, pokus o výdej: {count}."
            )
        self.physical_quantity -= count
        self.reserved_quantity = max(0, self.reserved_quantity - count)

    def add_physical(self, count: int) -> None:
        """Fyzický příjem na sklad."""
        if count <= 0:
            raise ValueError("Přijímané množství musí být kladné číslo.")
        self.physical_quantity += count

    def adjust_inventory(self, actual_count: int) -> int:
        """
        Inventurní vyrovnání (otevřený bod 3).
        Nastaví skutečný stav a vrátí rozdíl (kladný = přebytek, záporný = manko).
        """
        if actual_count < 0:
            raise ValueError("Skutečný napočítaný stav nesmí být záporný.")
        diff = actual_count - self.physical_quantity
        self.physical_quantity = actual_count
        # Pokud nová fyzická zásoba klesla pod rezervaci, omezíme rezervaci
        if self.reserved_quantity > self.physical_quantity:
            self.reserved_quantity = self.physical_quantity
        return diff

    def __repr__(self) -> str:
        return (
            f"<StockItem(warehouse_id={self.warehouse_id}, product_id={self.product_id}, "
            f"phys={self.physical_quantity}, res={self.reserved_quantity}, avail={self.available_quantity})>"
        )


class StockMovement:
    """
    Auditní záznam skladového pohybu.
    Každá změna stavu zásob musí být dohledatelná (pravidlo klienta).
    „Kde je ta káča, co jsem ji měl minulý týden.“
    """

    def __init__(
        self,
        movement_type: MovementType,
        product_id: str,
        quantity: int,
        source_warehouse_id: Optional[str] = None,
        target_warehouse_id: Optional[str] = None,
        variant_id: Optional[str] = None,
        reference_order_id: Optional[str] = None,
        note: str = "",
        performed_by: str = "Petr Doležal",
        created_at: Optional[datetime] = None,
        id: Optional[str] = None,
    ):
        if quantity <= 0:
            raise ValueError("Množství v pohybu musí být kladné.")

        self.id = id or str(uuid.uuid4())
        self.movement_type = movement_type
        self.product_id = product_id
        self.variant_id = variant_id
        self.quantity = int(quantity)
        self.source_warehouse_id = source_warehouse_id
        self.target_warehouse_id = target_warehouse_id
        self.reference_order_id = reference_order_id
        self.note = note.strip()
        self.performed_by = performed_by.strip()
        self.created_at = created_at or datetime.utcnow()

    def __repr__(self) -> str:
        return (
            f"<StockMovement(type={self.movement_type}, qty={self.quantity}, "
            f"src={self.source_warehouse_id}, tgt={self.target_warehouse_id})>"
        )
