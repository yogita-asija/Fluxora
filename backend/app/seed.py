"""Idempotent demo data. Run with: python -m app.seed"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Inventory, Order, OrderItem, Payment, Product, User
from app.models.enums import OrderStatus, PaymentStatus, UserRole

USERS = [
    ("admin@orderflow.local", "Demo Admin", UserRole.ADMIN),
    ("customer@orderflow.local", "Demo Customer", UserRole.CUSTOMER),
]

# (sku, name, description, price, on_hand, reorder_level)
PRODUCTS = [
    ("KB-MECH-01", "Mechanical Keyboard", "Hot-swappable 75% keyboard", "89.00", 120, 20),
    ("MS-WRL-02", "Wireless Mouse", "Ergonomic 2.4GHz mouse", "34.50", 200, 30),
    ("MN-27-4K", "27-inch 4K Monitor", "IPS panel, USB-C", "399.00", 35, 10),
    ("HS-ANC-03", "Noise-Cancelling Headset", "Over-ear, 30h battery", "149.99", 60, 15),
    ("WC-1080P", "1080p Webcam", "Autofocus, privacy shutter", "59.00", 8, 15),
    ("DK-USB-C", "USB-C Docking Station", "11-in-1 hub", "119.00", 45, 10),
    ("CH-ERG-07", "Ergonomic Chair", "Adjustable lumbar support", "329.00", 12, 5),
    ("LP-STD-08", "Aluminium Laptop Stand", "Foldable, 6 height levels", "29.00", 0, 25),
]

# (idempotency_key, user email, status, payment status, [(sku, quantity), ...])
ORDERS = [
    ("seed-order-1", "customer@orderflow.local", OrderStatus.PAID, PaymentStatus.CAPTURED,
     [("KB-MECH-01", 1), ("MS-WRL-02", 2)]),
    ("seed-order-2", "customer@orderflow.local", OrderStatus.PENDING, PaymentStatus.PENDING,
     [("MN-27-4K", 1)]),
    ("seed-order-3", "customer@orderflow.local", OrderStatus.FULFILLED, PaymentStatus.CAPTURED,
     [("HS-ANC-03", 1), ("DK-USB-C", 1)]),
]


def seed(db: Session) -> dict[str, int]:
    """Insert demo rows that don't exist yet. Safe to run repeatedly."""
    users = {}
    for email, full_name, role in USERS:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, full_name=full_name, role=role.value)
            db.add(user)
        users[email] = user

    products = {}
    for sku, name, description, price, on_hand, reorder in PRODUCTS:
        product = db.scalar(select(Product).where(Product.sku == sku))
        if product is None:
            product = Product(sku=sku, name=name, description=description, price=Decimal(price))
            product.inventory = Inventory(quantity_on_hand=on_hand, reorder_level=reorder)
            db.add(product)
        products[sku] = product
    db.flush()

    for key, email, order_status, payment_status, lines in ORDERS:
        if db.scalar(select(Order).where(Order.idempotency_key == key)):
            continue
        items = [
            OrderItem(product=products[sku], quantity=qty, unit_price=products[sku].price)
            for sku, qty in lines
        ]
        total = sum((i.unit_price * i.quantity for i in items), Decimal("0"))
        order = Order(
            user=users[email],
            status=order_status.value,
            total_amount=total,
            idempotency_key=key,
            items=items,
        )
        order.payments.append(Payment(amount=total, status=payment_status.value))
        db.add(order)

    db.commit()
    return {
        "users": db.query(User).count(),
        "products": db.query(Product).count(),
        "orders": db.query(Order).count(),
    }


def main() -> None:
    with SessionLocal() as db:
        counts = seed(db)
    print("Seed complete:", ", ".join(f"{k}={v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
