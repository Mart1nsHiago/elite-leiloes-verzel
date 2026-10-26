import os
from datetime import timedelta
from sqlalchemy import select
from .models import User, Lot, Bid
from .services import utcnow, close_lot
from .security import password_hash, random_alias, bid_signature, lot_seal


def seed(db):
    if db.scalar(select(User.id).limit(1)):
        return
    demo_password = os.getenv('DEMO_PASSWORD', 'Demo@2026')
    users = [
        User(name='Marina Leiloeira', email='leiloeiro@demo.com', role='auctioneer', public_alias='Leiloeiro', password_hash=password_hash(demo_password), balance_cents=0),
        User(name='Ana Licitante', email='ana@demo.com', role='bidder', public_alias='Licitante-A1B2', password_hash=password_hash(demo_password), balance_cents=350000),
        User(name='Bruno Licitante', email='bruno@demo.com', role='bidder', public_alias='Licitante-C3D4', password_hash=password_hash(demo_password), balance_cents=400000),
    ]
    db.add_all(users)
    db.flush()
    now = utcnow()
    lot1 = Lot(seller_id=users[0].id, external_id='/works/OL1003040W',
               title='Dom Casmurro', author='Machado de Assis',
               image_url='https://covers.openlibrary.org/b/id/14625893-L.jpg',
               description='Edição de colecionador. Leilão demonstrativo com lances registrados.',
               initial_cents=10000, increment_cents=2500, current_cents=0,
               starts_at=now-timedelta(minutes=20), ends_at=now+timedelta(hours=3), status='active')
    lot2 = Lot(seller_id=users[0].id, external_id='/works/OL10263W',
               title='O Pequeno Príncipe', author='Antoine de Saint-Exupéry',
               image_url='https://covers.openlibrary.org/b/id/10521270-L.jpg',
               description='Um clássico para sua coleção. Leilão ao vivo.',
               initial_cents=7500, increment_cents=1000, current_cents=0,
               starts_at=now-timedelta(minutes=10), ends_at=now+timedelta(hours=5), status='active')
    lot3 = Lot(seller_id=users[0].id, external_id='/works/OL1003017W',
               title='Memórias Póstumas de Brás Cubas', author='Machado de Assis',
               image_url='https://covers.openlibrary.org/b/id/12741324-L.jpg',
               description='Próxima oportunidade: edição especial.',
               initial_cents=12000, increment_cents=2000, current_cents=0,
               starts_at=now+timedelta(hours=1), ends_at=now+timedelta(hours=8), status='active')
    db.add_all([lot1, lot2, lot3])
    db.flush()
    for lot in [lot1, lot2, lot3]:
        lot.audit_seal = lot_seal(lot)
    for bidder, cents, created in [(users[1], 10000, now-timedelta(minutes=12)), (users[2], 12500, now-timedelta(minutes=7))]:
        bid = Bid(lot_id=lot1.id, bidder_id=bidder.id, bidder_alias=bidder.public_alias,
                  amount_cents=cents, created_at=created, previous_hash=lot1.audit_head, signature='')
        db.add(bid)
        db.flush()
        bid.signature = bid_signature(bid)
        lot1.current_cents = cents
        lot1.leader_id = bidder.id
        lot1.audit_count += 1
        lot1.audit_head = bid.signature
        lot1.audit_seal = lot_seal(lot1)
    # Histórico encerrado para demonstrar comprovante e liquidação sem esperar o relógio.
    closed = Lot(seller_id=users[0].id, external_id='/works/OL498556W',
                 title='A Metamorfose', author='Franz Kafka',
                 image_url='https://covers.openlibrary.org/b/id/8357150-L.jpg',
                 description='Peça arrematada de demonstração com comprovante público.',
                 initial_cents=9000, increment_cents=1000, current_cents=0,
                 starts_at=now-timedelta(days=2), ends_at=now-timedelta(days=1), status='active')
    db.add(closed)
    db.flush()
    closed.audit_seal = lot_seal(closed)
    old_bid = Bid(lot_id=closed.id, bidder_id=users[1].id,
                  bidder_alias=users[1].public_alias, amount_cents=9000,
                  created_at=now-timedelta(days=1, hours=12),
                  previous_hash='GENESIS', signature='')
    db.add(old_bid)
    db.flush()
    old_bid.signature = bid_signature(old_bid)
    closed.leader_id = users[1].id
    closed.current_cents = 9000
    closed.audit_count = 1
    closed.audit_head = old_bid.signature
    closed.audit_seal = lot_seal(closed)
    db.flush()
    close_lot(db, closed)
    db.commit()
