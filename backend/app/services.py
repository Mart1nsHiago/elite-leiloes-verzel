import uuid
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .models import Lot, Bid, User, WalletTransaction, Receipt
from .security import bid_signature, lot_seal, receipt_signature


def utcnow():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def lot_status(lot, now=None):
    now = now or utcnow()
    if lot.status == 'cancelled':
        return 'cancelled'
    if lot.status == 'closed' or aware(lot.ends_at) <= now:
        return 'closed'
    if aware(lot.starts_at) > now:
        return 'scheduled'
    return 'live'


def reserved_cents(db: Session, user_id: int, ignore_lot_id=None):
    stmt = select(func.coalesce(func.sum(Lot.current_cents), 0)).where(
        Lot.leader_id == user_id, Lot.status == 'active'
    )
    if ignore_lot_id is not None:
        stmt = stmt.where(Lot.id != ignore_lot_id)
    return int(db.scalar(stmt) or 0)


def wallet_dict(db, user):
    reserved = reserved_cents(db, user.id)
    return {'total_cents': user.balance_cents,
            'reserved_cents': reserved,
            'available_cents': user.balance_cents - reserved}


def audit(db: Session, lot: Lot):
    bids = db.scalars(select(Bid).where(Bid.lot_id == lot.id).order_by(Bid.id)).all()
    previous = 'GENESIS'
    issues = []
    for bid in bids:
        if bid.previous_hash != previous:
            issues.append(f'Lance #{bid.id}: elo anterior inválido')
        if bid_signature(bid) != bid.signature:
            issues.append(f'Lance #{bid.id}: assinatura inválida')
        previous = bid.signature
    if len(bids) != lot.audit_count:
        issues.append('Quantidade de lances não corresponde à âncora')
    if previous != lot.audit_head:
        issues.append('Hash final não corresponde à âncora')
    if lot.audit_seal != lot_seal(lot):
        issues.append('Selo do lote não confere')
    if bids:
        if lot.current_cents != bids[-1].amount_cents or lot.leader_id != bids[-1].bidder_id:
            issues.append('Líder ou preço atual diferente do último lance')
        if bids[0].amount_cents < lot.initial_cents:
            issues.append('Primeiro lance abaixo do inicial')
        for a, b in zip(bids, bids[1:]):
            if b.amount_cents < a.amount_cents + lot.increment_cents:
                issues.append(f'Lance #{b.id}: incremento inválido')
            if b.bidder_id == a.bidder_id:
                issues.append(f'Lance #{b.id}: autossuperação inválida')
    elif lot.current_cents != 0 or lot.leader_id is not None:
        issues.append('Lote sem lances apresenta vencedor ou preço')
    return {'valid': not issues, 'bid_count': len(bids), 'head': previous,
            'anchor': lot.audit_head, 'issues': issues,
            'bids': [{'id': b.id, 'alias': b.bidder_alias, 'amount_cents': b.amount_cents,
                      'created_at': aware(b.created_at).isoformat(),
                      'previous_hash': b.previous_hash, 'signature': b.signature} for b in bids]}


def serialize_lot(db, lot, current_user=None):
    status = lot_status(lot)
    return {'id': lot.id, 'title': lot.title, 'author': lot.author,
            'image_url': lot.image_url, 'description': lot.description,
            'external_id': lot.external_id, 'initial_cents': lot.initial_cents,
            'increment_cents': lot.increment_cents, 'current_cents': lot.current_cents,
            'bid_count': lot.audit_count, 'status': status,
            'starts_at': aware(lot.starts_at).isoformat(), 'ends_at': aware(lot.ends_at).isoformat(),
            'seller_id': lot.seller_id,
            'leader_alias': db.scalar(select(User.public_alias).where(User.id == lot.leader_id)) if lot.leader_id else None,
            'is_leader': bool(current_user and lot.leader_id == current_user.id),
            'is_owner': bool(current_user and lot.seller_id == current_user.id),
            'winner_alias': db.scalar(select(User.public_alias).where(User.id == lot.leader_id)) if status == 'closed' and lot.leader_id else None,
            'minimum_next_cents': lot.initial_cents if not lot.audit_count else lot.current_cents + lot.increment_cents}


def close_lot(db, lot):
    """Call inside a transaction with this lot SELECT FOR UPDATE locked."""
    if lot.status != 'active' or aware(lot.ends_at) > utcnow():
        return False
    if not audit(db, lot)['valid']:
        # Never settle a corrupted history.
        return False
    if lot.leader_id:
        user = db.scalar(select(User).where(User.id == lot.leader_id).with_for_update())
        seller = db.scalar(select(User).where(User.id == lot.seller_id).with_for_update())
        if user.balance_cents < lot.current_cents:
            return False
        user.balance_cents -= lot.current_cents
        seller.balance_cents += lot.current_cents
        db.add(WalletTransaction(user_id=user.id, lot_id=lot.id, amount_cents=-lot.current_cents, kind='purchase'))
        db.add(WalletTransaction(user_id=seller.id, lot_id=lot.id, amount_cents=lot.current_cents, kind='sale'))
        receipt = Receipt(lot_id=lot.id, winner_id=user.id,
                          public_token=uuid.uuid4().hex, buyer_alias=user.public_alias,
                          final_cents=lot.current_cents, closed_at=utcnow(), signature='')
        receipt.signature = receipt_signature(receipt)
        db.add(receipt)
    lot.status = 'closed'
    return True
