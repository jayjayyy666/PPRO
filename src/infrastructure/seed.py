"""
Syntetická data pro Dřevěnka s.r.o. (Petr Doležal).
Vygeneruje:
- 2 sklady: Centrální sklad Hradec Králové + Sezónní garáž Třebechovice
- 8 kategorií hraček
- 400 realistických produktů (dřevěných hraček) s rozdělením zásob mezi oba sklady
- Produkty pod minimem pro otestování červeného semaforu („co hoří“)
- Zákazníky a ukázkové objednávky / skladové pohyby
"""
import random
from datetime import datetime, timedelta
from src.infrastructure.database import SessionLocal, init_db
from src.infrastructure.models import (
    WarehouseModel,
    CategoryModel,
    ProductModel,
    ProductVariantModel,
    StockItemModel,
    StockMovementModel,
    CustomerModel,
    OrderModel,
    OrderItemModel,
)
from src.domain.models import MovementType, OrderStatus


def seed_database():
    init_db()
    db = SessionLocal()

    try:
        # Pokud již data existují, neprovádíme re-seed
        if db.query(ProductModel).count() >= 400:
            print("Databáze již obsahuje 400+ položek. Seed byl přeskočen.")
            return

        print("==> Inicializace syntetických dat pro Dřevěnka s.r.o. (400 položek)...")

        # 1. Sklady
        wh_hradec = WarehouseModel(
            code="HRADEC",
            name="Centrální sklad Hradec Králové",
            address="Pražská 124, 500 04 Hradec Králové",
            is_primary=True,
        )
        wh_garaz = WarehouseModel(
            code="TREBECHOVICE",
            name="Sezónní garáž Třebechovice",
            address="Orlická 88, 503 46 Třebechovice pod Orebem",
            is_primary=False,
        )
        db.add_all([wh_hradec, wh_garaz])
        db.flush()

        # 2. Kategorie
        categories_data = [
            ("Pro batolata", "Bezpečné hračky pro nejmenší z přírodního dřeva"),
            ("Dárky do 500 Kč", "Cenově dostupné a populární drobné dárky"),
            ("Dřevěné stavebnice a kostky", "Klasické bukové a borovicové kostky a stavebnice"),
            ("Tradiční hračky", "Káči, jo-ja, tahací zvířátka a lidové hračky"),
            ("Dřevěná vozidla a vláčky", "Kolejiště, mašinky, autíčka a traktory"),
            ("Domečky a figurky", "Dřevěné domečky pro panenky, zvířátka a postavičky"),
            ("Společenské a logické hry", "Dřevěné hlavolamy, šachy, puzzle a domino"),
            ("Sezónní dřevěné výrobky", "Vánoční ozdoby, velikonoční řehtačky, letní houpačky"),
        ]
        categories = []
        for name, desc in categories_data:
            cat = CategoryModel(name=name, description=desc)
            categories.append(cat)
            db.add(cat)
        db.flush()

        cat_batolata = categories[0]
        cat_darky = categories[1]
        cat_stavebnice = categories[2]
        cat_tradicni = categories[3]
        cat_vozidla = categories[4]
        cat_domecky = categories[5]
        cat_hry = categories[6]
        cat_sezonni = categories[7]

        # 3. Zákazníci
        customers_data = [
            ("Alena Nováková", "alena.novakova@priklad.cz", "+420 601 111 222", "Velké náměstí 15, Hradec Králové"),
            ("Martin Dvořák", "martin.dvorak@priklad.cz", "+420 602 333 444", "Na Rybníčku 8, Pardubice"),
            ("Jana Černá", "jana.cerna@priklad.cz", "+420 603 555 666", "Školní 240, Třebechovice pod Orebem"),
            ("Petr Kučera", "petr.kucera@priklad.cz", "+420 604 777 888", "Komenského 56, Jaroměř"),
            ("Lucie Veselá", "lucie.vesela@priklad.cz", "+420 605 999 000", "Bratří Čapků 12, Náchod"),
        ]
        customers = []
        for c_name, c_mail, c_phone, c_addr in customers_data:
            cust = CustomerModel(name=c_name, email=c_mail, phone=c_phone, address=c_addr, is_active=True)
            customers.append(cust)
            db.add(cust)
        db.flush()

        # 4. Produkty (celkem 400 položek dle reálného excelu klienta)
        # Položka č. 1: Ikonická Káča z příběhu klienta
        kaca = ProductModel(
            code="HRA-001",
            name="Tradiční dřevěná káča barevná",
            purchase_price=45.0,
            selling_price=120.0,
            description="Klasická točící se káča z bukového dřeva. Velmi oblíbená pro malé i velké.",
            min_stock_level=15,
        )
        kaca.categories = [cat_batolata, cat_darky, cat_tradicni]
        db.add(kaca)
        db.flush()

        # Varianty káči (řešení otevřeného bodu 4)
        v_red = ProductVariantModel(product_id=kaca.id, sku="HRA-001-RED", color_or_name="Červená")
        v_blu = ProductVariantModel(product_id=kaca.id, sku="HRA-001-BLU", color_or_name="Modrá")
        v_nat = ProductVariantModel(product_id=kaca.id, sku="HRA-001-NAT", color_or_name="Přírodní lak")
        db.add_all([v_red, v_blu, v_nat])
        db.flush()

        # Zásoby káči: v Hradci 12 ks, v garáži 25 ks (celkem 37 ks)
        stock_kaca_h = StockItemModel(
            warehouse_id=wh_hradec.id,
            product_id=kaca.id,
            physical_quantity=12,
            reserved_quantity=2,
        )
        stock_kaca_g = StockItemModel(
            warehouse_id=wh_garaz.id,
            product_id=kaca.id,
            physical_quantity=25,
            reserved_quantity=0,
        )
        db.add_all([stock_kaca_h, stock_kaca_g])

        # Seznam bází pro vygenerování 399 dalších hraček
        toy_bases = [
            ("Tahací kačenka s klapajícími křídly", 80.0, 240.0, [cat_batolata, cat_darky, cat_tradicni]),
            ("Dřevěný houpací kůň přírodní buk", 650.0, 1490.0, [cat_batolata, cat_tradicni]),
            ("Barevná dřevěná mašinka s vagonky", 140.0, 390.0, [cat_batolata, cat_darky, cat_vozidla]),
            ("Sada bukových kostek 50 ks v kyblíku", 160.0, 450.0, [cat_batolata, cat_darky, cat_stavebnice]),
            ("Dřevěný domeček pro panenky patrový", 890.0, 2190.0, [cat_domecky]),
            ("Zatloukací válec s dřevěnou paličkou", 95.0, 260.0, [cat_batolata, cat_darky]),
            ("Kuličková dráha dřevěná velká", 420.0, 990.0, [cat_stavebnice, cat_hry]),
            ("Dřevěné jo-jo malované", 30.0, 99.0, [cat_darky, cat_tradicni]),
            ("Skládací věž z dřevěných kroužků", 75.0, 199.0, [cat_batolata, cat_darky]),
            ("Dřevěný traktor s vlečkou", 130.0, 340.0, [cat_vozidla, cat_darky]),
            ("Dřevěná vkládačka geometrické tvary", 85.0, 220.0, [cat_batolata, cat_darky, cat_hry]),
            ("Šachy dřevěné vyřezávané v krabičce", 350.0, 890.0, [cat_hry]),
            ("Dřevěné domino se zvířátky", 65.0, 180.0, [cat_batolata, cat_darky, cat_hry]),
            ("Velikonoční řehtačka velká", 45.0, 130.0, [cat_darky, cat_sezonni, cat_tradicni]),
            ("Vánoční dřevěný betlém skládací", 280.0, 690.0, [cat_sezonni, cat_domecky]),
            ("Dřevěná houpačka prkno s lany", 120.0, 320.0, [cat_sezonni, cat_darky]),
            ("Dřevěné pexeso Krkonošská zvířátka", 70.0, 190.0, [cat_darky, cat_hry]),
            ("Dřevěný hasičský vůz s žebříkem", 150.0, 390.0, [cat_vozidla, cat_darky]),
            ("Dřevěné puzzle mapa České republiky", 110.0, 290.0, [cat_hry, cat_darky]),
            ("Loutkové divadélko přenosné dřevěné", 550.0, 1290.0, [cat_domecky, cat_tradicni]),
        ]

        # Generujeme zbývajících 399 položek
        random.seed(42)  # Deterministická syntetická data
        for i in range(2, 401):
            base_idx = (i - 2) % len(toy_bases)
            base_name, base_buy, base_sell, base_cats = toy_bases[base_idx]
            sub_id = (i - 2) // len(toy_bases) + 1

            code = f"HRA-{i:03d}"
            name = f"{base_name} (typ {sub_id})" if sub_id > 1 else base_name
            # Mírná variabilita cen
            factor = 1.0 + ((i % 10) - 5) * 0.03
            buy_price = round(base_buy * factor, 1)
            sell_price = round(base_sell * factor, 1)
            min_stock = random.choice([5, 8, 10, 15, 20])

            prod = ProductModel(
                code=code,
                name=name,
                purchase_price=buy_price,
                selling_price=sell_price,
                description=f"Ručně opracovaná česká dřevěná hračka z masivu. Kód položky: {code}.",
                min_stock_level=min_stock,
            )
            prod.categories = base_cats
            db.add(prod)
            db.flush()

            # Skladové stavy:
            # 10 % položek schválně nastavíme pod minimum pro červený semafor („hoří“)
            is_under_min = (i % 10 == 0)
            if is_under_min:
                h_phys = random.randint(0, min(2, min_stock - 1))
                g_phys = random.randint(0, min(1, min_stock - 1))
            else:
                h_phys = random.randint(min_stock, min_stock * 3)
                g_phys = random.randint(0, min_stock * 2)

            reserved = random.randint(0, min(h_phys, 2)) if h_phys > 0 else 0

            db.add(
                StockItemModel(
                    warehouse_id=wh_hradec.id,
                    product_id=prod.id,
                    physical_quantity=h_phys,
                    reserved_quantity=reserved,
                )
            )
            db.add(
                StockItemModel(
                    warehouse_id=wh_garaz.id,
                    product_id=prod.id,
                    physical_quantity=g_phys,
                    reserved_quantity=0,
                )
            )

        # 5. Ukázková historie pohybů (Audit log dle požadavku 5)
        movements_data = [
            (MovementType.RECEIPT, kaca.id, 50, wh_hradec.id, None, "Příjem z truhlárny"),
            (MovementType.TRANSFER_OUT, kaca.id, 25, wh_hradec.id, wh_garaz.id, "Převoz do zimní garáže Třebechovice"),
            (MovementType.TRANSFER_IN, kaca.id, 25, wh_hradec.id, wh_garaz.id, "Naskladnění v garáži"),
            (MovementType.INVENTORY_ADJUSTMENT, kaca.id, 2, wh_garaz.id, wh_garaz.id, "Inventura garáže: nalezeny 2 ks za skříní"),
        ]
        for m_type, p_id, qty, src, tgt, note in movements_data:
            db.add(
                StockMovementModel(
                    movement_type=m_type,
                    product_id=p_id,
                    quantity=qty,
                    source_warehouse_id=src,
                    target_warehouse_id=tgt,
                    note=note,
                    performed_by="Petr Doležal",
                    created_at=datetime.utcnow() - timedelta(days=random.randint(1, 10)),
                )
            )

        # 6. Ukázkové objednávky pro statistiku měsíčního obratu
        for idx, cust in enumerate(customers[:3]):
            order = OrderModel(
                order_number=f"OBJ-2026-000{idx+1}",
                customer_id=cust.id,
                order_date=datetime.utcnow() - timedelta(days=idx * 2),
                status=OrderStatus.SHIPPED if idx > 0 else OrderStatus.CONFIRMED,
                note="Objednávka z e-shopu",
                total_price=0.0,
            )
            db.add(order)
            db.flush()

            # Položka objednávky
            item = OrderItemModel(
                order_id=order.id,
                product_id=kaca.id,
                warehouse_id=wh_hradec.id,
                quantity=2,
                unit_price=120.0,
            )
            order.items.append(item)
            order.total_price = 240.0

            if order.status == OrderStatus.SHIPPED:
                order.shipped_at = datetime.utcnow()
                db.add(
                    StockMovementModel(
                        movement_type=MovementType.DISPATCH,
                        product_id=kaca.id,
                        quantity=2,
                        source_warehouse_id=wh_hradec.id,
                        reference_order_id=order.id,
                        note=f"Výdej pro objednávku {order.order_number}",
                        performed_by="Petr Doležal",
                    )
                )

        db.commit()
        print("==> Úspěšně nahráno 400 produktů, 2 sklady a syntetická data do databáze!")

    except Exception as e:
        db.rollback()
        print(f"Chyba při seedování: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
