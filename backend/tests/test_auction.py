from datetime import timedelta
from sqlalchemy import select, update
from app.db import SessionLocal
from app.models import Lot, Bid, Receipt, User
from app.services import utcnow, close_lot, audit


def test_seeded_lots_and_audit_public(client):
    data = client.get('/api/lots').json()
    assert len(data) >= 4
    assert any(x['status'] == 'live' and x['bid_count'] >= 2 for x in data)
    report = client.get('/api/lots/1/audit').json()
    assert report['valid'] is True and report['bid_count'] == 2
    assert all('email' not in bid for bid in report['bids'])


def test_authentication_and_public_only_bidder_registration(client):
    invalid = client.post('/api/auth/login', json={'email': 'ana@demo.com', 'password':'wrong'})
    assert invalid.status_code == 401
    registered = client.post('/api/auth/register',json={'name':'Teste Cliente','email':'novo@example.com','password':'Senha2026!'} )
    assert registered.status_code == 201
    assert registered.json()['user']['role'] == 'bidder'
    assert registered.json()['user']['public_alias'].startswith('Licitante-')
    assert client.get('/api/wallet').status_code == 401


def test_wallet_and_outbid_releases_reservation(client, auth):
    ana = auth()
    bruno = auth('bruno@demo.com')
    first = client.get('/api/wallet', headers=bruno).json()
    assert first['reserved_cents'] == 12500
    result = client.post('/api/lots/1/bids',headers=ana,json={'amount_cents':15000})
    assert result.status_code == 201, result.text
    assert client.get('/api/wallet',headers=ana).json()['reserved_cents'] == 15000
    assert client.get('/api/wallet',headers=bruno).json()['reserved_cents'] == 0
    assert client.get('/api/lots/1/audit').json()['valid'] is True


def test_increment_leader_no_self_bid_rejections(client, auth):
    bruno=auth('bruno@demo.com')
    ana=auth()
    assert client.post('/api/lots/1/bids',headers=bruno,json={'amount_cents':15000}).status_code == 409
    assert client.post('/api/lots/1/bids',headers=ana,json={'amount_cents':12501}).status_code == 409
    assert client.post('/api/lots/1/bids',headers=ana,json={'amount_cents':15000}).status_code == 201
    assert client.post('/api/lots/1/bids',headers=ana,json={'amount_cents':20000}).status_code == 409


def test_insufficient_balance_and_deposit(client, auth):
    # Fresh account starts at zero.
    d=client.post('/api/auth/register',json={'name':'Sem Saldo','email':'semsaldo@demo.com','password':'12345678'})
    headers={'Authorization': 'Bearer '+d.json()['access_token']}
    assert client.post('/api/lots/2/bids',headers=headers,json={'amount_cents':7500}).status_code == 409
    deposited=client.post('/api/wallet/deposit',headers=headers,json={'amount_cents':10000})
    assert deposited.status_code == 200
    bid=client.post('/api/lots/2/bids',headers=headers,json={'amount_cents':7500})
    assert bid.status_code == 201
    wallet=client.get('/api/wallet',headers=headers).json()
    assert wallet['total_cents'] == 10000 and wallet['reserved_cents'] == 7500 and wallet['available_cents'] == 2500


def test_auctioneer_cannot_bid_but_can_create_and_cancel_empty_lot(client, auth):
    seller=auth('leiloeiro@demo.com')
    assert client.post('/api/lots/1/bids',headers=seller,json={'amount_cents':20000}).status_code == 403
    now=utcnow()
    data={'external_id':'/works/OL10263W','title':'Outro exemplar de O Pequeno Príncipe',
          'author':'Antoine de Saint-Exupéry','initial_cents':1000,'increment_cents':100,
          'starts_at':now.isoformat(),'ends_at':(now+timedelta(hours=2)).isoformat()}
    created=client.post('/api/lots',headers=seller,json=data)
    assert created.status_code==201,created.text
    id=created.json()['id']
    assert client.delete(f'/api/lots/{id}',headers=seller).status_code==200
    assert all(l['id']!=id for l in client.get('/api/lots').json())
    assert client.delete('/api/lots/1',headers=seller).status_code==409


def test_anti_sniping_adds_two_minutes(client, auth):
    with SessionLocal() as db:
        lot=db.get(Lot,2)
        old_end=utcnow()+timedelta(seconds=50)
        lot.ends_at=old_end
        db.commit()
    ana=auth()
    result=client.post('/api/lots/2/bids',headers=ana,json={'amount_cents':7500})
    assert result.status_code==201,result.text
    assert result.json()['extended'] is True
    new_end=result.json()['lot']['ends_at']
    from app.services import aware
    from datetime import datetime
    assert abs((datetime.fromisoformat(new_end)-old_end).total_seconds()-120)<0.1


def test_closed_lot_rejects_bid(client,auth):
    ana=auth()
    assert client.post('/api/lots/4/bids',headers=ana,json={'amount_cents':20000}).status_code==409


def test_closed_receipt_public_and_private_fields(client,auth):
    ana=auth()
    activity=client.get('/api/me/activity',headers=ana).json()
    item=next(x for x in activity if x['won'])
    result=client.get('/api/receipts/'+item['receipt_token'])
    assert result.status_code==200
    assert result.json()['valid'] is True
    assert result.json()['winner_alias']=='Licitante-A1B2'
    assert 'email' not in result.text and 'Ana Licitante' not in result.text
    assert client.get('/api/lots/4/audit').json()['valid'] is True


def test_db_tampering_detected(client):
    with SessionLocal() as db:
        db.execute(update(Bid).where(Bid.id==1).values(amount_cents=777))
        db.commit()
    data=client.get('/api/lots/1/audit').json()
    assert data['valid'] is False
    assert any('assinatura' in issue.lower() for issue in data['issues'])


def test_db_history_delete_detected(client):
    with SessionLocal() as db:
        bid=db.get(Bid,2)
        db.delete(bid)
        db.commit()
    assert client.get('/api/lots/1/audit').json()['valid'] is False


def test_db_insert_detected(client):
    with SessionLocal() as db:
        db.add(Bid(lot_id=1,bidder_id=2,bidder_alias='Licitante-A1B2',amount_cents=50000,
                   created_at=utcnow(),previous_hash='invalid',signature='fake'))
        db.commit()
    assert client.get('/api/lots/1/audit').json()['valid'] is False


def test_settlement_is_idempotent_and_transfers_cents(client):
    with SessionLocal() as db:
        lot=db.get(Lot,1)
        lot.ends_at=utcnow()-timedelta(seconds=2)
        db.commit()
        user_before=db.get(User,3).balance_cents
        seller_before=db.get(User,1).balance_cents
        lot=db.scalar(select(Lot).where(Lot.id==1).with_for_update())
        assert close_lot(db,lot) is True
        db.commit()
        assert db.get(User,3).balance_cents==user_before-12500
        assert db.get(User,1).balance_cents==seller_before+12500
        assert close_lot(db,lot) is False
        receipt=db.scalar(select(Receipt).where(Receipt.lot_id==1))
        assert receipt is not None
        assert audit(db,lot)['valid'] is True


def test_external_catalog_failure_does_not_affect_lots(client):
    # Local persisted operations do not fetch the external catalog.
    assert client.get('/api/lots').status_code==200
    assert client.get('/api/lots/1/audit').status_code==200
    assert client.get('/api/receipts/nonexistent').status_code==404


def test_websocket_broadcast_after_accepted_bid(client, auth):
    ana = auth()
    with client.websocket_connect('/api/lots/1/ws') as websocket:
        assert websocket.receive_json()['type'] == 'connected'
        response = client.post('/api/lots/1/bids', headers=ana, json={'amount_cents':15000})
        assert response.status_code == 201
        event = websocket.receive_json()
        assert event == {'type':'lot_updated', 'lot_id':1}


def test_catalog_cached_fallback_on_api_outage(client, monkeypatch):
    import httpx
    class OfflineClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def get(self, *args, **kwargs):
            raise httpx.ConnectError('Offline')
    monkeypatch.setattr('app.main.httpx.AsyncClient', OfflineClient)
    response = client.get('/api/catalog/search?q=Dom')
    assert response.status_code == 200
    assert response.json()['source'] == 'cached_reference'
    assert any(item['title']=='Dom Casmurro' for item in response.json()['items'])
    assert client.get('/api/lots').status_code == 200
