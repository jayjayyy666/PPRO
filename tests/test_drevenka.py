"""
Automatizované unit a integrační testy pro projekt Dřevěnka s.r.o.
Testuje klíčová obchodní pravidla a požadavky klienta:
- Požadavek 4: Odmítnutí objednávky, na kterou nejsou zásoby
- Pravidlo: Vydat víc, než je na skladě, nesmí jít (zákaz záporného stavu)
- Pravidlo: Cena v objednávce se nesmí zpětně změnit při úpravě ceníku
- Pravidlo: Zákazník se nemaže (soft-delete)
- Požadavek 1: Vazba M:N pro kategorie
- Požadavek 6: Přesun mezi sklady (garáž -> Hradec)
- Požadavek 7: Semafor minimálních zásob
- Požadavek 8: Měsíční obrat po kategoriích
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.database import Base
from src.infrastructure.models import (
    WarehouseModel,
    CategoryModel,
    ProductModel,
    StockItemModel,
    OrderModel,
    OrderItemModel,
    CustomerModel,
)
from src.domain.models import MovementType, OrderStatus
from src.application.services.inventory_service import (
    InventoryService,
    InsufficientStockException,
)
from src.application.services.order_service import (
    OrderService,
    OrderRejectionException,
)
from src.application.services.reporting_service import ReportingService
from src.application.dto.inventory_dto import OrderCreateDTO, OrderItemCreateDTO


@pytest.fixture
def db_session():
    """In-memory SQLite session pro rychlé a izolované testy."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()

    # Příprava základních entit
    wh_h = WarehouseModel(code="HRADEC", name="Centrální sklad Hradec Králové", is_primary=True)
    wh_g = WarehouseModel(code="TREBECHOVICE", name="Sezónní garáž Třebechovice", is_primary=False)
    cat1 = CategoryModel(name="Pro batolata")
    cat2 = CategoryModel(name="Dárky do 500 Kč")

    session.add_all([wh_h, wh_g, cat1, cat2])
    session.flush()

    # Káča (produkt zařazený do obou kategorií současně - M:N)
    kaca = ProductModel(
        code="HRA-001",
        name="Tradiční dřevěná káča barevná",
        purchase_price=45.0,
        selling_price=120.0,
        min_stock_level=10,
    )
    kaca.categories = [cat1, cat2]
    session.add(kaca)
    session.flush()

    # Počáteční stav: v Hradci 5 ks, v garáži 20 ks
    stock_h = StockItemModel(warehouse_id=wh_h.id, product_id=kaca.id, physical_quantity=5, reserved_quantity=0)
    stock_g = StockItemModel(warehouse_id=wh_g.id, product_id=kaca.id, physical_quantity=20, reserved_quantity=0)
    session.add_all([stock_h, stock_g])
    session.commit()

    yield session
    session.close()


def test_product_multiple_categories(db_session):
    """Ověření požadavku 1: Produkt patří do několika kategorií naráz (vazba M:N)."""
    kaca = db_session.query(ProductModel).filter(ProductModel.code == "HRA-001").first()
    assert len(kaca.categories) == 2
    category_names = [c.name for c in kaca.categories]
    assert "Pro batolata" in category_names
    assert "Dárky do 500 Kč" in category_names


def test_order_rejection_insufficient_stock(db_session):
    """
    Ověření požadavku 4: Odmítnutí objednávky, na kterou nejsou zásoby.
    „Tohle je důvod, proč se to celé dělá.“
    V Hradci je pouze 5 ks. Pokus o objednávku 10 ks musí okamžitě selhat!
    """
    order_service = OrderService(db_session)
    kaca = db_session.query(ProductModel).filter(ProductModel.code == "HRA-001").first()
    wh_h = db_session.query(WarehouseModel).filter(WarehouseModel.code == "HRADEC").first()

    order_dto = OrderCreateDTO(
        customer_name="Jan Novák",
        customer_email="jan.novak@priklad.cz",
        items=[OrderItemCreateDTO(product_id=kaca.id, warehouse_id=wh_h.id, quantity=10)],
    )

    with pytest.raises(OrderRejectionException) as excinfo:
        order_service.create_order(order_dto)

    assert "nedostatek skladových zásob" in str(excinfo.value).lower()
    # Ověříme, že žádná objednávka nebyla uložena a zásoby zůstaly nezměněny
    assert db_session.query(OrderModel).count() == 0
    stock_h = db_session.query(StockItemModel).filter(StockItemModel.warehouse_id == wh_h.id).first()
    assert stock_h.physical_quantity == 5
    assert stock_h.reserved_quantity == 0


def test_order_success_and_atomic_reservation(db_session):
    """
    Ověření úspěšného přijetí a atomické rezervace (Otevřený bod 2).
    Objednání 3 ks z 5 dostupných: fyzicky zůstává 5, rezervováno je 3, volno 2.
    """
    order_service = OrderService(db_session)
    kaca = db_session.query(ProductModel).filter(ProductModel.code == "HRA-001").first()
    wh_h = db_session.query(WarehouseModel).filter(WarehouseModel.code == "HRADEC").first()

    order_dto = OrderCreateDTO(
        customer_name="Jan Novák",
        customer_email="jan.novak@priklad.cz",
        items=[OrderItemCreateDTO(product_id=kaca.id, warehouse_id=wh_h.id, quantity=3)],
    )

    order = order_service.create_order(order_dto)
    assert order.status == OrderStatus.CONFIRMED
    assert order.total_price == 3 * 120.0

    stock_h = db_session.query(StockItemModel).filter(StockItemModel.warehouse_id == wh_h.id).first()
    assert stock_h.physical_quantity == 5
    assert stock_h.reserved_quantity == 3
    assert (stock_h.physical_quantity - stock_h.reserved_quantity) == 2


def test_price_immutability_in_order(db_session):
    """
    Ověření pravidla: Cena v objednávce se nesmí zpětně změnit, když se upraví ceník.
    """
    order_service = OrderService(db_session)
    kaca = db_session.query(ProductModel).filter(ProductModel.code == "HRA-001").first()
    wh_h = db_session.query(WarehouseModel).filter(WarehouseModel.code == "HRADEC").first()

    order_dto = OrderCreateDTO(
        customer_name="Petr Svoboda",
        customer_email="petr.svoboda@priklad.cz",
        items=[OrderItemCreateDTO(product_id=kaca.id, warehouse_id=wh_h.id, quantity=2)],
    )
    order = order_service.create_order(order_dto)
    assert order.total_price == 240.0
    item = order.items[0]
    assert item.unit_price == 120.0

    # Zvýšíme cenu káči v ceníku na 180 Kč
    kaca.selling_price = 180.0
    db_session.commit()

    # V již vytvořené objednávce musí zůstat původní cena 120 Kč a celkem 240 Kč!
    reloaded_order = db_session.query(OrderModel).filter(OrderModel.id == order.id).first()
    assert reloaded_order.items[0].unit_price == 120.0
    assert reloaded_order.total_price == 240.0


def test_inter_warehouse_transfer(db_session):
    """
    Ověření požadavku 6: Přesun mezi sklady (garáž Třebechovice -> Hradec Králové).
    Převeze se 10 ks z 20 ks v garáži do Hradce.
    """
    inv_service = InventoryService(db_session)
    kaca = db_session.query(ProductModel).filter(ProductModel.code == "HRA-001").first()
    wh_h = db_session.query(WarehouseModel).filter(WarehouseModel.code == "HRADEC").first()
    wh_g = db_session.query(WarehouseModel).filter(WarehouseModel.code == "TREBECHOVICE").first()

    # Před převodem: Hradec = 5, Garáž = 20
    inv_service.transfer_stock(
        product_id=kaca.id,
        from_warehouse_id=wh_g.id,
        to_warehouse_id=wh_h.id,
        quantity=10,
        note="Závoz na hlavní sklad",
    )

    stock_h = db_session.query(StockItemModel).filter(StockItemModel.warehouse_id == wh_h.id).first()
    stock_g = db_session.query(StockItemModel).filter(StockItemModel.warehouse_id == wh_g.id).first()

    # Po převodu: Hradec = 15, Garáž = 10
    assert stock_h.physical_quantity == 15
    assert stock_g.physical_quantity == 10

    # Ověření auditní stopy (požadavek 5)
    movements = inv_service.get_movements_history()
    assert len(movements) == 2
    types = [m.movement_type for m in movements]
    assert MovementType.TRANSFER_OUT in types
    assert MovementType.TRANSFER_IN in types


def test_prevent_overdraft_transfer(db_session):
    """Ověření pravidla: Vydat víc, než je na skladě, nesmí jít ani při meziskladovém přesunu."""
    inv_service = InventoryService(db_session)
    kaca = db_session.query(ProductModel).filter(ProductModel.code == "HRA-001").first()
    wh_h = db_session.query(WarehouseModel).filter(WarehouseModel.code == "HRADEC").first()
    wh_g = db_session.query(WarehouseModel).filter(WarehouseModel.code == "TREBECHOVICE").first()

    # V garáži je 20 ks, pokus o převoz 25 ks musí selhat
    with pytest.raises(InsufficientStockException):
        inv_service.transfer_stock(
            product_id=kaca.id,
            from_warehouse_id=wh_g.id,
            to_warehouse_id=wh_h.id,
            quantity=25,
        )


def test_customer_soft_delete(db_session):
    """Ověření pravidla: Zákazník se nemaže, protože se vrací s reklamacemi."""
    customer = CustomerModel(name="Marie Zelená", email="marie@priklad.cz", is_active=True)
    db_session.add(customer)
    db_session.commit()

    # Zákazník se pouze deaktivuje (soft-delete)
    customer.is_active = False
    db_session.commit()

    reloaded = db_session.query(CustomerModel).filter(CustomerModel.id == customer.id).first()
    assert reloaded is not None
    assert reloaded.is_active is False


def test_reporting_low_stock_alert(db_session):
    """
    Ověření požadavku 7: Minimální zásoba (Semafor na dashboardu).
    Minimální zásoba káči je 10 ks. Celkem je na skladě Hradec 5 ks (bez garáže),
    pokud v garáži nastavíme 0 ks, musí být označen jako RED.
    """
    rep_service = ReportingService(db_session)
    kaca = db_session.query(ProductModel).filter(ProductModel.code == "HRA-001").first()
    wh_g = db_session.query(WarehouseModel).filter(WarehouseModel.code == "TREBECHOVICE").first()

    # Vynulujeme garáž, v Hradci je 5 ks, minimum je 10 ks -> Celkem 5 < 10 => RED alert!
    stock_g = db_session.query(StockItemModel).filter(StockItemModel.warehouse_id == wh_g.id).first()
    stock_g.physical_quantity = 0
    db_session.commit()

    alerts = rep_service.get_low_stock_alerts()
    assert len(alerts) >= 1
    kaca_alert = next((a for a in alerts if a.product_id == kaca.id), None)
    assert kaca_alert is not None
    assert kaca_alert.urgency_status == "RED"
    assert kaca_alert.current_physical_stock == 5
    assert kaca_alert.recommended_reorder > 0


def test_monthly_category_revenue(db_session):
    """
    Ověření požadavku 8: Obrat po kategoriích za měsíc.
    """
    order_service = OrderService(db_session)
    rep_service = ReportingService(db_session)
    kaca = db_session.query(ProductModel).filter(ProductModel.code == "HRA-001").first()
    wh_h = db_session.query(WarehouseModel).filter(WarehouseModel.code == "HRADEC").first()

    order_dto = OrderCreateDTO(
        customer_name="Karel Hynek",
        customer_email="karel.hynek@priklad.cz",
        items=[OrderItemCreateDTO(product_id=kaca.id, warehouse_id=wh_h.id, quantity=2)],
    )
    order = order_service.create_order(order_dto)
    order_service.ship_order(order.id)

    now = order.order_date
    revenues = rep_service.get_monthly_category_revenue(year=now.year, month=now.month)

    # Protože káča patří do 'Pro batolata' i 'Dárky do 500 Kč', v obou musí být tržba 240 Kč
    batolata = next((r for r in revenues if r.category_name == "Pro batolata"), None)
    darky = next((r for r in revenues if r.category_name == "Dárky do 500 Kč"), None)

    assert batolata is not None and batolata.total_revenue == 240.0
    assert darky is not None and darky.total_revenue == 240.0
