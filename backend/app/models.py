from datetime import datetime, timezone
from sqlalchemy import String, Integer, BigInteger, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    public_alias: Mapped[str] = mapped_column(String(25), unique=True)
    balance_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Lot(Base):
    __tablename__ = 'lots'
    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    seller = relationship('User', foreign_keys=[seller_id])
    external_id: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(250))
    author: Mapped[str] = mapped_column(String(200), default='')
    image_url: Mapped[str] = mapped_column(String(700), default='')
    description: Mapped[str] = mapped_column(Text, default='')
    initial_cents: Mapped[int] = mapped_column(BigInteger)
    increment_cents: Mapped[int] = mapped_column(BigInteger)
    current_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    leader_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default='active')  # active / cancelled / closed
    audit_count: Mapped[int] = mapped_column(Integer, default=0)
    audit_head: Mapped[str] = mapped_column(String(64), default='GENESIS')
    audit_seal: Mapped[str] = mapped_column(String(64), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    bids = relationship('Bid', back_populates='lot', order_by='Bid.id')


class Bid(Base):
    __tablename__ = 'bids'
    id: Mapped[int] = mapped_column(primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey('lots.id'), index=True)
    bidder_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    bidder = relationship('User')
    bidder_alias: Mapped[str] = mapped_column(String(25))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    previous_hash: Mapped[str] = mapped_column(String(64))
    signature: Mapped[str] = mapped_column(String(64))
    lot = relationship('Lot', back_populates='bids')


class WalletTransaction(Base):
    __tablename__ = 'wallet_transactions'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey('lots.id'), nullable=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Receipt(Base):
    __tablename__ = 'receipts'
    id: Mapped[int] = mapped_column(primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey('lots.id'), unique=True)
    winner_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    public_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    buyer_alias: Mapped[str] = mapped_column(String(25))
    final_cents: Mapped[int] = mapped_column(BigInteger)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    signature: Mapped[str] = mapped_column(String(64))
