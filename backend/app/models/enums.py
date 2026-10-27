from enum import StrEnum


class UserRole(StrEnum):
    CUSTOMER = "customer"
    ADMIN = "admin"


class OrderStatus(StrEnum):
    PENDING = "pending"
    RESERVED = "reserved"
    PAID = "paid"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"
    FAILED = "failed"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"


class ReservationStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    RELEASED = "released"
    EXPIRED = "expired"


class OutboxStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"
