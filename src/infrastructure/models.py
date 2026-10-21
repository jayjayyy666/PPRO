"""
SQLAlchemy ORM modely pro Dřevěnka s.r.o.
Vynucení klíčových obchodních pravidel:
- Zákaz záporného stavu: CheckConstraint('physical_quantity >= 0') a CheckConstraint('reserved_quantity >= 0')
- Fixace prodejních cen v objednávkách
- Vazba M:N pro kategorie produktů
- Nemazání zákazníků
"""
from __future__ import annotations
from datetime import datetime, timezone
import uuid
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Table,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from src.infrastructure.database import Base


# Vazební tabulka M:N: ProductCategory
product_categories = Table(
    "product_categories",
    Base.metadata,
    Column("product_id", String(36), ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", String(36), ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)


class CategoryModel(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")

    products: Mapped[list[ProductModel]] = relationship("ProductModel", secondary=product_categories, back_populates="categories")


class ProductVariantModel(Base):
    __tablename__ = "product_variants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    sku: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    color_or_name: Mapped[str] = mapped_column(String(50), nullable=False)

    product: Mapped[ProductModel] = relationship("ProductModel", back_populates="variants")


class ProductModel(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    purchase_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    selling_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    description: Mapped[str] = mapped_column(Text, default="")
    min_stock_level: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    categories: Mapped[list[CategoryModel]] = relationship("CategoryModel", secondary=product_categories, back_populates="products")
    variants: Mapped[list[ProductVariantModel]] = relationship("ProductVariantModel", back_populates="product", cascade="all, delete-orphan")
    stock_items: Mapped[list[StockItemModel]] = relationship("StockItemModel", back_populates="product", cascade="all, delete-orphan")


class WarehouseModel(Base):
    __tablename__ = "warehouses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(String(200), default="")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    stock_items: Mapped[list[StockItemModel]] = relationship("StockItemModel", back_populates="warehouse", cascade="all, delete-orphan")


class StockItemModel(Base):
    __tablename__ = "stock_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    warehouse_id: Mapped[str] = mapped_column(String(36), ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)

    physical_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    warehouse: Mapped[WarehouseModel] = relationship("WarehouseModel", back_populates="stock_items")
    product: Mapped[ProductModel] = relationship("ProductModel", back_populates="stock_items")
    variant: Mapped[ProductVariantModel | None] = relationship("ProductVariantModel")

    __table_args__ = (
        UniqueConstraint("warehouse_id", "product_id", "variant_id", name="uq_warehouse_product_variant"),
        CheckConstraint("physical_quantity >= 0", name="chk_stock_physical_nonnegative"),
        CheckConstraint("reserved_quantity >= 0", name="chk_stock_reserved_nonnegative"),
    )


class StockMovementModel(Base):
    __tablename__ = "stock_movements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    movement_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    source_warehouse_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True)
    target_warehouse_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True)
    reference_order_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    performed_by: Mapped[str] = mapped_column(String(100), default="Petr Doležal")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    product: Mapped[ProductModel] = relationship("ProductModel")
    source_warehouse: Mapped[WarehouseModel | None] = relationship("WarehouseModel", foreign_keys=[source_warehouse_id])
    target_warehouse: Mapped[WarehouseModel | None] = relationship("WarehouseModel", foreign_keys=[target_warehouse_id])


class CustomerModel(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(50), default="")
    address: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # Nemazání historie: soft-delete
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    orders: Mapped[list[OrderModel]] = relationship("OrderModel", back_populates="customer")


class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    order_date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="CONFIRMED", index=True)
    total_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    note: Mapped[str] = mapped_column(Text, default="")
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    customer: Mapped[CustomerModel] = relationship("CustomerModel", back_populates="orders")
    items: Mapped[list[OrderItemModel]] = relationship("OrderItemModel", back_populates="order", cascade="all, delete-orphan")


class OrderItemModel(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False)
    variant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("product_variants.id"), nullable=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), ForeignKey("warehouses.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # Zafixovaná historická cena v době prodeje!

    order: Mapped[OrderModel] = relationship("OrderModel", back_populates="items")
    product: Mapped[ProductModel] = relationship("ProductModel")
    warehouse: Mapped[WarehouseModel] = relationship("WarehouseModel")
