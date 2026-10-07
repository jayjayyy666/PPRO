"""
SQLAlchemy ORM modely pro Dřevěnka s.r.o.
Vynucení klíčových obchodních pravidel:
- Zákaz záporného stavu: CheckConstraint('physical_quantity >= 0') a CheckConstraint('reserved_quantity >= 0')
- Fixace prodejních cen v objednávkách
- Vazba M:N pro kategorie produktů
- Nemazání zákazníků
"""
from datetime import datetime
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
from sqlalchemy.orm import relationship
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

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(255), default="")

    products = relationship("ProductModel", secondary=product_categories, back_populates="categories")


class ProductVariantModel(Base):
    __tablename__ = "product_variants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    sku = Column(String(50), nullable=False, unique=True)
    color_or_name = Column(String(50), nullable=False)

    product = relationship("ProductModel", back_populates="variants")


class ProductModel(Base):
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    purchase_price = Column(Float, nullable=False, default=0.0)
    selling_price = Column(Float, nullable=False, default=0.0)
    description = Column(Text, default="")
    min_stock_level = Column(Integer, nullable=False, default=5)
    created_at = Column(DateTime, default=datetime.utcnow)

    categories = relationship("CategoryModel", secondary=product_categories, back_populates="products")
    variants = relationship("ProductVariantModel", back_populates="product", cascade="all, delete-orphan")
    stock_items = relationship("StockItemModel", back_populates="product", cascade="all, delete-orphan")


class WarehouseModel(Base):
    __tablename__ = "warehouses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    address = Column(String(200), default="")
    is_primary = Column(Boolean, default=False)

    stock_items = relationship("StockItemModel", back_populates="warehouse", cascade="all, delete-orphan")


class StockItemModel(Base):
    __tablename__ = "stock_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    warehouse_id = Column(String(36), ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id = Column(String(36), ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)

    physical_quantity = Column(Integer, nullable=False, default=0)
    reserved_quantity = Column(Integer, nullable=False, default=0)

    warehouse = relationship("WarehouseModel", back_populates="stock_items")
    product = relationship("ProductModel", back_populates="stock_items")
    variant = relationship("ProductVariantModel")

    __table_args__ = (
        UniqueConstraint("warehouse_id", "product_id", "variant_id", name="uq_warehouse_product_variant"),
        CheckConstraint("physical_quantity >= 0", name="chk_stock_physical_nonnegative"),
        CheckConstraint("reserved_quantity >= 0", name="chk_stock_reserved_nonnegative"),
    )


class StockMovementModel(Base):
    __tablename__ = "stock_movements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    movement_type = Column(String(50), nullable=False, index=True)
    product_id = Column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id = Column(String(36), ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)
    quantity = Column(Integer, nullable=False)
    source_warehouse_id = Column(String(36), ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True)
    target_warehouse_id = Column(String(36), ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True)
    reference_order_id = Column(String(36), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    note = Column(Text, default="")
    performed_by = Column(String(100), default="Petr Doležal")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    product = relationship("ProductModel")
    source_warehouse = relationship("WarehouseModel", foreign_keys=[source_warehouse_id])
    target_warehouse = relationship("WarehouseModel", foreign_keys=[target_warehouse_id])


class CustomerModel(Base):
    __tablename__ = "customers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(150), nullable=False)
    email = Column(String(150), nullable=False, unique=True, index=True)
    phone = Column(String(50), default="")
    address = Column(String(255), default="")
    is_active = Column(Boolean, default=True)  # Nemazání historie: soft-delete
    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("OrderModel", back_populates="customer")


class OrderModel(Base):
    __tablename__ = "orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_number = Column(String(50), nullable=False, unique=True, index=True)
    customer_id = Column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    order_date = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String(50), nullable=False, default="CONFIRMED", index=True)
    total_price = Column(Float, nullable=False, default=0.0)
    note = Column(Text, default="")
    shipped_at = Column(DateTime, nullable=True)

    customer = relationship("CustomerModel", back_populates="orders")
    items = relationship("OrderItemModel", back_populates="order", cascade="all, delete-orphan")


class OrderItemModel(Base):
    __tablename__ = "order_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False)
    variant_id = Column(String(36), ForeignKey("product_variants.id"), nullable=True)
    warehouse_id = Column(String(36), ForeignKey("warehouses.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False, default=0.0)  # Zafixovaná historická cena v době prodeje!

    order = relationship("OrderModel", back_populates="items")
    product = relationship("ProductModel")
    warehouse = relationship("WarehouseModel")
