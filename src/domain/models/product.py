"""
Doménový model pro produkty, varianty a kategorie hraček (Dřevěnka s.r.o.).
"""
from datetime import datetime
from typing import List, Optional
import uuid


class Category:
    """Kategorie zboží (např. 'Pro batolata', 'Dárky do 500 Kč')."""

    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        id: Optional[str] = None,
    ):
        self.id = id or str(uuid.uuid4())
        self.name = name.strip()
        self.description = description.strip() if description else ""

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name='{self.name}')>"


class ProductVariant:
    """
    Varianta produktu (řešení otevřeného bodu 4: Varianty produktu).
    Umožňuje evidovat barvy (např. táž káča v červené, modré, přírodní barvě).
    """

    def __init__(
        self,
        product_id: str,
        sku: str,
        color_or_name: str,
        id: Optional[str] = None,
    ):
        self.id = id or str(uuid.uuid4())
        self.product_id = product_id
        self.sku = sku.strip().upper()
        self.color_or_name = color_or_name.strip()

    def __repr__(self) -> str:
        return f"<ProductVariant(sku='{self.sku}', color='{self.color_or_name}')>"


class Product:
    """
    Produkt (dřevěná hračka).
    Obsahuje název, kód, popis, nákupní a prodejní cenu a minimální zásobu.
    Produkt může patřit do více kategorií naráz (vazba M:N).
    """

    def __init__(
        self,
        code: str,
        name: str,
        purchase_price: float,
        selling_price: float,
        description: str = "",
        min_stock_level: int = 5,
        categories: Optional[List[Category]] = None,
        variants: Optional[List[ProductVariant]] = None,
        id: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ):
        if purchase_price < 0 or selling_price < 0:
            raise ValueError("Ceny produktu nesmí být záporné.")
        if min_stock_level < 0:
            raise ValueError("Minimální hladina zásob nesmí být záporná.")
        if not code.strip():
            raise ValueError("Kód produktu (SKU) je povinný.")
        if not name.strip():
            raise ValueError("Název produktu je povinný.")

        self.id = id or str(uuid.uuid4())
        self.code = code.strip().upper()
        self.name = name.strip()
        self.description = description.strip()
        self.purchase_price = float(purchase_price)
        self.selling_price = float(selling_price)
        self.min_stock_level = int(min_stock_level)
        self.categories = categories or []
        self.variants = variants or []
        self.created_at = created_at or datetime.utcnow()

    def add_category(self, category: Category) -> None:
        if not any(c.id == category.id for c in self.categories):
            self.categories.append(category)

    def remove_category(self, category_id: str) -> None:
        self.categories = [c for c in self.categories if c.id != category_id]

    def has_category(self, category_name: str) -> bool:
        return any(c.name.lower() == category_name.lower() for c in self.categories)

    def __repr__(self) -> str:
        return f"<Product(code='{self.code}', name='{self.name}', price={self.selling_price})>"
