import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

PH = PasswordHasher(time_cost=2, memory_cost=16384, parallelism=2)


def secret():
    return os.getenv('JWT_SECRET', 'development-only-jwt-secret-change-in-production')


def audit_secret():
    return os.getenv('AUDIT_SECRET', 'development-only-audit-secret-change-in-production')


def password_hash(value):
    return PH.hash(value)


def verify_password(password, hashed):
    try:
        return PH.verify(hashed, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def token(user_id):
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': str(user_id), 'iat': now, 'exp': now + timedelta(hours=24)}, secret(), algorithm='HS256')


def user_id_from_token(value):
    try:
        return int(jwt.decode(value, secret(), algorithms=['HS256'])['sub'])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None


def signed(payload):
    normalized = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hmac.new(audit_secret().encode(), normalized.encode(), hashlib.sha256).hexdigest()


def iso(value):
    # SQLite can return naive datetimes; values are always stored as UTC.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec='microseconds')


def bid_signature(bid):
    return signed({'v': 1, 'id': bid.id, 'lot_id': bid.lot_id,
                   'bidder_id': bid.bidder_id, 'alias': bid.bidder_alias,
                   'cents': bid.amount_cents, 'timestamp': iso(bid.created_at),
                   'previous': bid.previous_hash})


def lot_seal(lot):
    return signed({'v': 1, 'lot_id': lot.id, 'count': lot.audit_count,
                   'head': lot.audit_head, 'current': lot.current_cents,
                   'leader': lot.leader_id})


def receipt_signature(receipt):
    return signed({'v': 1, 'token': receipt.public_token, 'lot': receipt.lot_id,
                   'winner': receipt.winner_id, 'alias': receipt.buyer_alias,
                   'amount': receipt.final_cents, 'closed_at': iso(receipt.closed_at)})


def random_alias():
    return 'Licitante-' + uuid.uuid4().hex[:8].upper()
