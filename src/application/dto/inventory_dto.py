"""
DTO objekty pro aplikační vrstvu (Pydantic modely pro validaci a API).
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class CategoryDTO(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""


class ProductVariantDTO(BaseModel):
    id: str
    sku: str
    color_or_name: str


class ProductCreateDTO(BaseModel):
    code: str = Field(..., description="Unikátní kód produktu (SKU)")
    name: str = Field(..., description="Název produktu")
    purchase_price: float = Field(..., ge=0, description="Nákupní cena bez DPH")
    selling_price: float = Field(..., ge=0, description="Prodejní cena pro zákazníka")
    description: str = Field("", description="Podrobný popis")
    min_stock_level: int = Field(5, ge=0, description="Minimální doporučená zásoba")
    category_ids: List[str] = Field(default_factory=list, description="Kategorie produktu")


class ProductStockDetailDTO(BaseModel):
    warehouse_id: str
    warehouse_name: str
    warehouse_code: str
    physical_quantity: int
    reserved_quantity: int
    available_quantity: int


class ProductResponseDTO(BaseModel):
    id: str
    code: str
    name: str
    purchase_price: float
    selling_price: float
    description: str
    min_stock_level: int
    total_physical_stock: int
    total_reserved_stock: int
    total_available_stock: int
    is_below_minimum: bool
    categories: List[CategoryDTO]
    stock_details: List[ProductStockDetailDTO]


class OrderItemCreateDTO(BaseModel):
    product_id: str
    warehouse_id: Optional[str] = None  # Pokud není zadán, preferuje se centrální sklad Hradec
    quantity: int = Field(..., gt=0, description="Počet kusů")


class OrderCreateDTO(BaseModel):
    customer_name: str = Field(..., description="Jméno a příjmení zákazníka")
    customer_email: str = Field(..., description="E-mail zákazníka")
    customer_phone: str = Field("", description="Telefon zákazníka")
    customer_address: str = Field("", description="Doručovací adresa")
    items: List[OrderItemCreateDTO] = Field(..., min_length=1, description="Položky objednávky")
    note: str = Field("", description="Poznámka k objednávce")


class OrderItemResponseDTO(BaseModel):
    id: str
    product_id: str
    product_code: str
    product_name: str
    warehouse_id: str
    warehouse_name: str
    quantity: int
    unit_price: float
    total_price: float


class OrderResponseDTO(BaseModel):
    id: str
    order_number: str
    customer_name: str
    customer_email: str
    status: str
    total_price: float
    note: str
    order_date: datetime
    items: List[OrderItemResponseDTO]


class StockTransferDTO(BaseModel):
    product_id: str = Field(..., description="ID převáděného produktu")
    from_warehouse_id: str = Field(..., description="Zdrojový sklad (např. Garáž Třebechovice)")
    to_warehouse_id: str = Field(..., description="Cílový sklad (např. Centrální sklad Hradec)")
    quantity: int = Field(..., gt=0, description="Počet převáděných kusů")
    note: str = Field("", description="Důvod přesunu (např. Sezónní naskladnění)")
    performed_by: str = Field("Petr Doležal", description="Zodpovědná osoba")


class InventoryAdjustmentDTO(BaseModel):
    product_id: str = Field(..., description="ID produktu")
    warehouse_id: str = Field(..., description="Sklad k inventuře")
    actual_quantity: int = Field(..., ge=0, description="Skutečně napočítaný stav na polici")
    note: str = Field(..., description="Zdůvodnění manka/přebytku")
    performed_by: str = Field("Petr Doležal", description="Zodpovědná osoba")


class StockMovementResponseDTO(BaseModel):
    id: str
    movement_type: str
    product_name: str
    product_code: str
    quantity: int
    source_warehouse_name: Optional[str] = None
    target_warehouse_name: Optional[str] = None
    note: str
    performed_by: str
    created_at: datetime


class LowStockAlertDTO(BaseModel):
    product_id: str
    product_code: str
    product_name: str
    current_physical_stock: int
    current_available_stock: int
    min_stock_level: int
    recommended_reorder: int
    urgency_status: str  # RED (pod minimem), YELLOW (blíží se minimu)
    categories: List[str]


class CategoryRevenueDTO(BaseModel):
    category_id: str
    category_name: str
    total_orders_count: int
    total_items_sold: int
    total_revenue: float
