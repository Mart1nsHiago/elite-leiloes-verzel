"""Elite Leilões API. All monetary amounts are integer cents; dates are UTC."""
import asyncio
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
import httpx
from fastapi import FastAPI, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import Base, SessionLocal, engine, get_db
from .models import User, Lot, Bid, Receipt, WalletTransaction
from .security import (password_hash, verify_password, token, user_id_from_token,
                       bid_signature, lot_seal, receipt_signature, random_alias)
from .services import (utcnow, aware, lot_status, reserved_cents, wallet_dict,
                       audit, serialize_lot, close_lot)
from .seed import seed

DB = Annotated[Session, Depends(get_db)]
BEARER = HTTPBearer(auto_error=False)


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class RegisterBody(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class DepositBody(BaseModel):
    amount_cents: int = Field(ge=100, le=1000000)


class BidBody(BaseModel):
    amount_cents: int = Field(gt=0)


class LotBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    external_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=2, max_length=250)
    author: str = Field(default='', max_length=200)
    image_url: str = Field(default='', max_length=700)
    description: str = Field(default='', max_length=2000)
    initial_cents: int = Field(ge=100)
    increment_cents: int = Field(ge=100)
    starts_at: datetime
    ends_at: datetime


class ConnectionManager:
    def __init__(self):
        self.rooms: dict[int, set[WebSocket]] = {}

    async def connect(self, lot_id, websocket):
        await websocket.accept()
        self.rooms.setdefault(lot_id, set()).add(websocket)

    def disconnect(self, lot_id, websocket):
        self.rooms.get(lot_id, set()).discard(websocket)

    async def broadcast(self, lot_id, kind):
        for websocket in list(self.rooms.get(lot_id, set())):
            try:
                await websocket.send_json({'type': kind, 'lot_id': lot_id})
            except Exception:
                self.disconnect(lot_id, websocket)


manager = ConnectionManager()


async def settlement_worker():
    while True:
        try:
            with SessionLocal() as db:
                ids = db.scalars(select(Lot.id).where(Lot.status == 'active', Lot.ends_at <= utcnow()).limit(40)).all()
            for lot_id in ids:
                with SessionLocal() as db:
                    try:
                        lot = db.scalar(select(Lot).where(Lot.id == lot_id).with_for_update())
                        if lot and close_lot(db, lot):
                            db.commit()
                            await manager.broadcast(lot_id, 'lot_updated')
                        else:
                            db.rollback()
                    except Exception:
                        db.rollback()
        except Exception:
            # The next cycle retries; app remains available if the database is briefly down.
            pass
        await asyncio.sleep(4)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv('ENVIRONMENT') == 'production':
        if len(os.getenv('JWT_SECRET', '')) < 32 or len(os.getenv('AUDIT_SECRET', '')) < 32:
            raise RuntimeError('Configure JWT_SECRET e AUDIT_SECRET com pelo menos 32 caracteres.')
        if os.getenv('DEMO_PASSWORD', 'Demo@2026') == 'Demo@2026':
            raise RuntimeError('Configure DEMO_PASSWORD em produção.')
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)
    worker = asyncio.create_task(settlement_worker())
    yield
    worker.cancel()
    with suppress(asyncio.CancelledError):
        await worker


app = FastAPI(title='Elite Leilões API', version='1.0.0', lifespan=lifespan)
origins = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',')
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in origins], allow_credentials=False,
                   allow_methods=['GET','POST','DELETE','OPTIONS'], allow_headers=['*'])


def optional_user(db: Session, credentials: HTTPAuthorizationCredentials | None = Depends(BEARER)):
    if not credentials:
        return None
    uid = user_id_from_token(credentials.credentials)
    return db.get(User, uid) if uid is not None else None


def me(db: DB, credentials: HTTPAuthorizationCredentials | None = Depends(BEARER)):
    user = optional_user(db, credentials)
    if user is None:
        raise HTTPException(401, 'Entre na sua conta para continuar.')
    return user


def bidder_only(user):
    if user.role != 'bidder':
        raise HTTPException(403, 'Apenas licitantes podem realizar esta operação.')


def seller_only(user):
    if user.role != 'auctioneer':
        raise HTTPException(403, 'Apenas leiloeiros podem realizar esta operação.')


def public_user(user):
    return {'id': user.id, 'name': user.name, 'email': user.email, 'role': user.role,
            'public_alias': user.public_alias}


@app.get('/api/health')
def health():
    return {'status': 'ok'}


@app.post('/api/auth/login')
def login(data: LoginBody, db: DB):
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, 'E-mail ou senha inválidos.')
    return {'access_token': token(user.id), 'user': public_user(user)}


@app.post('/api/auth/register', status_code=201)
def register(data: RegisterBody, db: DB):
    user = User(name=data.name.strip(), email=str(data.email).lower(),
                password_hash=password_hash(data.password), role='bidder',
                public_alias=random_alias(), balance_cents=0)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'E-mail já cadastrado.')
    db.refresh(user)
    return {'access_token': token(user.id), 'user': public_user(user)}


@app.get('/api/auth/me')
def get_me(user: Annotated[User, Depends(me)]):
    return public_user(user)


@app.get('/api/wallet')
def get_wallet(db: DB, user: Annotated[User, Depends(me)]):
    return wallet_dict(db, user)


@app.post('/api/wallet/deposit')
def deposit(data: DepositBody, db: DB, user: Annotated[User, Depends(me)]):
    bidder_only(user)
    locked = db.scalar(select(User).where(User.id == user.id).with_for_update())
    locked.balance_cents += data.amount_cents
    db.add(WalletTransaction(user_id=user.id, amount_cents=data.amount_cents, kind='demo_deposit'))
    db.commit()
    return wallet_dict(db, locked)


@app.get('/api/catalog/search')
async def search_books(q: str = '', limit: int = 9):
    q = q.strip()
    if len(q) < 2:
        return {'items': [], 'source': 'openlibrary'}
    if len(q) > 120:
        raise HTTPException(422, 'Busca muito longa.')
    limit = max(1, min(12, limit))
    try:
        async with httpx.AsyncClient(timeout=7.0) as client:
            result = await client.get('https://openlibrary.org/search.json', params={
                'q': q, 'limit': limit, 'fields': 'key,title,author_name,first_publish_year,cover_i'})
            result.raise_for_status()
            docs = result.json().get('docs', [])
        return {'source': 'openlibrary', 'items': [
            {'external_id': row['key'], 'title': row['title'],
             'author': ', '.join(row.get('author_name', [])[:2]),
             'year': row.get('first_publish_year'),
             'image_url': f"https://covers.openlibrary.org/b/id/{row['cover_i']}-L.jpg" if row.get('cover_i') else ''}
            for row in docs if row.get('key') and row.get('title')
        ]}
    except (httpx.HTTPError, ValueError, KeyError):
        # Snapshot de referência: viabiliza demonstração completa sem depender da API.
        offline = [
            {'external_id': '/works/OL1003040W', 'title': 'Dom Casmurro', 'author': 'Machado de Assis', 'year': 1899, 'image_url': 'https://covers.openlibrary.org/b/id/14625893-L.jpg'},
            {'external_id': '/works/OL10263W', 'title': 'O Pequeno Príncipe', 'author': 'Antoine de Saint-Exupéry', 'year': 1943, 'image_url': 'https://covers.openlibrary.org/b/id/10521270-L.jpg'},
            {'external_id': '/works/OL498556W', 'title': 'A Metamorfose', 'author': 'Franz Kafka', 'year': 1915, 'image_url': 'https://covers.openlibrary.org/b/id/8357150-L.jpg'},
            {'external_id': '/works/OL1003017W', 'title': 'Memórias Póstumas de Brás Cubas', 'author': 'Machado de Assis', 'year': 1881, 'image_url': 'https://covers.openlibrary.org/b/id/12741324-L.jpg'},
        ]
        matches = [x for x in offline if q.lower() in (x['title'] + ' ' + x['author']).lower()]
        return {'source': 'cached_reference', 'items': matches[:limit], 'warning': 'Open Library indisponível; exibindo referências locais previamente catalogadas.'}


@app.get('/api/lots')
def list_lots(db: DB, status: str = 'all', q: str = '',
              credentials: HTTPAuthorizationCredentials | None = Depends(BEARER)):
    user = optional_user(db, credentials)
    lots = db.scalars(select(Lot).where(Lot.status != 'cancelled').order_by(Lot.created_at.desc())).all()
    items = [serialize_lot(db, lot, user) for lot in lots]
    if status != 'all':
        items = [x for x in items if x['status'] == status]
    if q.strip():
        items = [x for x in items if q.lower() in (x['title'] + ' ' + x['author']).lower()]
    return items


@app.get('/api/me/lots')
def my_lots(db: DB, user: Annotated[User, Depends(me)]):
    seller_only(user)
    lots = db.scalars(select(Lot).where(Lot.seller_id == user.id).order_by(Lot.id.desc())).all()
    return [serialize_lot(db, lot, user) for lot in lots]


@app.post('/api/lots', status_code=201)
def create_lot(data: LotBody, db: DB, user: Annotated[User, Depends(me)]):
    seller_only(user)
    start, end = aware(data.starts_at), aware(data.ends_at)
    if end <= utcnow() or end <= start:
        raise HTTPException(422, 'Término deve ser posterior ao início e estar no futuro.')
    if end - start > timedelta(days=30):
        raise HTTPException(422, 'Duração máxima de 30 dias.')
    lot = Lot(seller_id=user.id, external_id=data.external_id,
              title=data.title, author=data.author, image_url=data.image_url,
              description=data.description, initial_cents=data.initial_cents,
              increment_cents=data.increment_cents, starts_at=start, ends_at=end,
              current_cents=0, audit_count=0, audit_head='GENESIS', status='active')
    db.add(lot)
    db.flush()
    lot.audit_seal = lot_seal(lot)
    db.commit()
    return serialize_lot(db, lot, user)


@app.get('/api/lots/{lot_id}')
def get_lot(lot_id: int, db: DB,
            credentials: HTTPAuthorizationCredentials | None = Depends(BEARER)):
    lot = db.get(Lot, lot_id)
    if not lot or lot.status == 'cancelled':
        raise HTTPException(404, 'Lote não encontrado.')
    return serialize_lot(db, lot, optional_user(db, credentials))


@app.delete('/api/lots/{lot_id}')
def cancel_lot(lot_id: int, db: DB, user: Annotated[User, Depends(me)]):
    seller_only(user)
    lot = db.scalar(select(Lot).where(Lot.id == lot_id).with_for_update())
    if not lot or lot.seller_id != user.id:
        raise HTTPException(404, 'Lote não encontrado.')
    if lot.audit_count or lot.status != 'active':
        raise HTTPException(409, 'Somente lotes ativos sem nenhum lance podem ser cancelados.')
    lot.status = 'cancelled'
    db.commit()
    return {'ok': True}


@app.get('/api/lots/{lot_id}/audit')
def public_audit(lot_id: int, db: DB):
    lot = db.get(Lot, lot_id)
    if lot is None:
        raise HTTPException(404, 'Lote não encontrado.')
    report = audit(db, lot)
    return {'lot_id': lot_id, 'title': lot.title, **report}


@app.post('/api/lots/{lot_id}/bids', status_code=201)
async def place_bid(lot_id: int, data: BidBody, db: DB, user: Annotated[User, Depends(me)]):
    bidder_only(user)
    try:
        # PostgreSQL row lock prevents two concurrent accepted bids against stale prices.
        lot = db.scalar(select(Lot).where(Lot.id == lot_id).with_for_update())
        if not lot or lot.status == 'cancelled':
            raise HTTPException(404, 'Lote não encontrado.')
        locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
        now = utcnow()
        current_status = lot_status(lot, now)
        if current_status == 'scheduled':
            raise HTTPException(409, 'Este lote ainda não foi iniciado.')
        if current_status != 'live':
            raise HTTPException(409, 'Este lote já foi encerrado.')
        if lot.seller_id == user.id:
            raise HTTPException(403, 'Leiloeiro não pode dar lances.')
        if lot.leader_id == user.id:
            raise HTTPException(409, 'Você já está ganhando. Aguarde outro licitante.')
        expected = lot.initial_cents if lot.audit_count == 0 else lot.current_cents + lot.increment_cents
        if data.amount_cents < expected:
            raise HTTPException(409, f'Lance abaixo do mínimo. Valor mínimo: {expected} centavos.')
        available = locked_user.balance_cents - reserved_cents(db, user.id)
        if data.amount_cents > available:
            raise HTTPException(409, 'Saldo disponível insuficiente para este lance.')
        if not audit(db, lot)['valid']:
            raise HTTPException(409, 'Histórico comprometido: lote bloqueado para novos lances.')
        bid = Bid(lot_id=lot.id, bidder_id=user.id, bidder_alias=user.public_alias,
                  amount_cents=data.amount_cents, created_at=now,
                  previous_hash=lot.audit_head, signature='')
        db.add(bid)
        db.flush()
        bid.signature = bid_signature(bid)
        lot.leader_id = user.id
        lot.current_cents = data.amount_cents
        lot.audit_head = bid.signature
        lot.audit_count += 1
        extended = False
        if aware(lot.ends_at) - now <= timedelta(minutes=2):
            lot.ends_at = aware(lot.ends_at) + timedelta(minutes=2)
            extended = True
        lot.audit_seal = lot_seal(lot)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Conflito de lance. Atualize o lote e tente novamente.')
    await manager.broadcast(lot_id, 'lot_updated')
    return {'ok': True, 'bid_id': bid.id, 'extended': extended,
            'lot': serialize_lot(db, lot, user), 'wallet': wallet_dict(db, user)}


@app.get('/api/me/activity')
def my_activity(db: DB, user: Annotated[User, Depends(me)]):
    bidder_only(user)
    bids = db.scalars(select(Bid).where(Bid.bidder_id == user.id).order_by(Bid.created_at.desc())).all()
    lot_ids = list(dict.fromkeys(b.lot_id for b in bids))
    entries = []
    for lot_id in lot_ids:
        lot = db.get(Lot, lot_id)
        receipt = db.scalar(select(Receipt).where(Receipt.lot_id == lot_id))
        entries.append({'lot': serialize_lot(db, lot, user),
                        'won': bool(receipt and receipt.winner_id == user.id),
                        'receipt_token': receipt.public_token if receipt and receipt.winner_id == user.id else None})
    return entries


@app.get('/api/receipts/{public_token}')
def get_receipt(public_token: str, db: DB):
    receipt = db.scalar(select(Receipt).where(Receipt.public_token == public_token))
    if not receipt:
        raise HTTPException(404, 'Comprovante não encontrado.')
    lot = db.get(Lot, receipt.lot_id)
    verification = audit(db, lot)
    return {'token': receipt.public_token, 'lot_id': receipt.lot_id,
            'title': lot.title, 'winner_alias': receipt.buyer_alias,
            'final_cents': receipt.final_cents,
            'closed_at': aware(receipt.closed_at).isoformat(),
            'valid': receipt_signature(receipt) == receipt.signature and verification['valid'],
            'signature': receipt.signature}


@app.websocket('/api/lots/{lot_id}/ws')
async def lot_socket(websocket: WebSocket, lot_id: int):
    # Public socket only carries notification IDs; clients fetch canonical DB state via GET.
    await manager.connect(lot_id, websocket)
    try:
        await websocket.send_json({'type': 'connected', 'lot_id': lot_id})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(lot_id, websocket)


# Docker / Render: serve a aplicação React compilada no mesmo domínio da API.
# Em desenvolvimento, Vite serve o front-end e encaminha /api para a API local.
dist_directory = Path(os.getenv('FRONTEND_DIST', str(Path(__file__).resolve().parents[2] / 'frontend' / 'dist')))
if dist_directory.is_dir():
    app.mount('/', StaticFiles(directory=str(dist_directory), html=True), name='frontend')
