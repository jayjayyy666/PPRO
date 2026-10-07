"""
Aplikační služba pro správu skladových zásob, meziskladové převody a inventury.
"""
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from src.domain.models import MovementType
from src.infrastructure.models import (
    WarehouseModel,
    ProductModel,
    StockItemModel,
    StockMovementModel,
)


class InsufficientStockException(Exception):
    """Výjimka vyhozená při pokusu o výdej/převod nad rámec dostupných zásob."""
    pass


class InventoryService:
    def __init__(self, db: Session):
        self.db = db

    def get_warehouses(self) -> List[WarehouseModel]:
        return self.db.query(WarehouseModel).order_by(WarehouseModel.is_primary.desc()).all()

    def get_primary_warehouse(self) -> WarehouseModel:
        wh = self.db.query(WarehouseModel).filter(WarehouseModel.is_primary == True).first()
        if not wh:
            wh = self.db.query(WarehouseModel).first()
        return wh

    def get_stock_item(self, warehouse_id: str, product_id: str) -> Optional[StockItemModel]:
        return (
            self.db.query(StockItemModel)
            .filter(
                StockItemModel.warehouse_id == warehouse_id,
                StockItemModel.product_id == product_id,
            )
            .first()
        )

    def get_or_create_stock_item(self, warehouse_id: str, product_id: str) -> StockItemModel:
        item = self.get_stock_item(warehouse_id, product_id)
        if not item:
            item = StockItemModel(
                warehouse_id=warehouse_id,
                product_id=product_id,
                physical_quantity=0,
                reserved_quantity=0,
            )
            self.db.add(item)
            self.db.flush()
        return item

    def transfer_stock(
        self,
        product_id: str,
        from_warehouse_id: str,
        to_warehouse_id: str,
        quantity: int,
        note: str = "",
        performed_by: str = "Petr Doležal",
    ) -> Tuple[StockItemModel, StockItemModel]:
        """
        Přesun mezi sklady (požadavek klienta 6: zimní garáž -> Hradec).
        Atomická operace:
        1. Ověří dostatek volných zásob na zdrojovém skladu (Vydat víc, než je na skladě, nesmí jít).
        2. Poníží fyzický stav ve zdrojovém skladu.
        3. Navýší fyzický stav v cílovém skladu.
        4. Zapíše 2 auditní pohyby: TRANSFER_OUT a TRANSFER_IN (požadavek 5).
        """
        if quantity <= 0:
            raise ValueError("Množství k přesunu musí být kladné.")
        if from_warehouse_id == to_warehouse_id:
            raise ValueError("Zdrojový a cílový sklad musí být odlišné.")

        # Pesimistické zamykání řádku na zdrojovém skladu
        source_item = (
            self.db.query(StockItemModel)
            .filter(
                StockItemModel.warehouse_id == from_warehouse_id,
                StockItemModel.product_id == product_id,
            )
            .with_for_update()
            .first()
        )

        if not source_item:
            raise InsufficientStockException("Položka na zdrojovém skladu vůbec neexistuje.")

        available = source_item.physical_quantity - source_item.reserved_quantity
        if available < quantity:
            raise InsufficientStockException(
                f"Nelze provést přesun: na zdrojovém skladě je k dispozici pouze {available} ks "
                f"(fyzicky: {source_item.physical_quantity}, rezervováno: {source_item.reserved_quantity}), "
                f"požadováno k přesunu: {quantity} ks."
            )

        target_item = self.get_or_create_stock_item(to_warehouse_id, product_id)

        # Provedení fyzického přesunu
        source_item.physical_quantity -= quantity
        target_item.physical_quantity += quantity

        # Zápis auditních pohybů
        product = self.db.query(ProductModel).filter(ProductModel.id == product_id).first()
        prod_name = product.name if product else product_id

        mov_out = StockMovementModel(
            movement_type=MovementType.TRANSFER_OUT,
            product_id=product_id,
            quantity=quantity,
            source_warehouse_id=from_warehouse_id,
            target_warehouse_id=to_warehouse_id,
            note=f"Meziskladový přesun: {note or 'Převoz zboží'}",
            performed_by=performed_by,
        )
        mov_in = StockMovementModel(
            movement_type=MovementType.TRANSFER_IN,
            product_id=product_id,
            quantity=quantity,
            source_warehouse_id=from_warehouse_id,
            target_warehouse_id=to_warehouse_id,
            note=f"Příjem z přesunu: {note or 'Převoz zboží'}",
            performed_by=performed_by,
        )

        self.db.add(mov_out)
        self.db.add(mov_in)
        self.db.commit()

        return source_item, target_item

    def adjust_inventory(
        self,
        product_id: str,
        warehouse_id: str,
        actual_quantity: int,
        note: str,
        performed_by: str = "Petr Doležal",
    ) -> int:
        """
        Inventurní vyrovnání (řešení otevřeného bodu 3: Záporný stav a garáž).
        Záporný stav se zakáže (CHECK >= 0). Nesrovnalost se srovná inventurním protokolem.
        Zaznamená se rozdíl (manko / přebytek) a auditní záznam.
        """
        if actual_quantity < 0:
            raise ValueError("Fyzický stav při inventuře nesmí být záporný.")

        stock_item = self.get_or_create_stock_item(warehouse_id, product_id)
        old_physical = stock_item.physical_quantity
        diff = actual_quantity - old_physical

        stock_item.physical_quantity = actual_quantity
        if stock_item.reserved_quantity > stock_item.physical_quantity:
            stock_item.reserved_quantity = stock_item.physical_quantity

        diff_text = f"Přebytek +{diff} ks" if diff >= 0 else f"Manko {diff} ks"
        movement = StockMovementModel(
            movement_type=MovementType.INVENTORY_ADJUSTMENT,
            product_id=product_id,
            quantity=abs(diff) if diff != 0 else 0,
            source_warehouse_id=warehouse_id,
            target_warehouse_id=warehouse_id,
            note=f"Inventura: {diff_text}. Důvod: {note}",
            performed_by=performed_by,
        )
        self.db.add(movement)
        self.db.commit()

        return diff

    def get_movements_history(self, limit: int = 100) -> List[StockMovementModel]:
        """Získání historie pohybů pro dohledání (požadavek 5: Kde je ta káča)."""
        return (
            self.db.query(StockMovementModel)
            .order_by(StockMovementModel.created_at.desc())
            .limit(limit)
            .all()
        )
