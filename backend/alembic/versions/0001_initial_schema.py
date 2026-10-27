"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-10-26 19:27:20.624064
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('outbox_events',
    sa.Column('aggregate_type', sa.String(length=64), nullable=False),
    sa.Column('aggregate_id', sa.Uuid(), nullable=False),
    sa.Column('event_type', sa.String(length=128), nullable=False),
    sa.Column('payload', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('status', sa.String(length=32), server_default='pending', nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("status IN ('pending', 'published', 'failed')", name=op.f('ck_outbox_events_status_valid')),
    sa.CheckConstraint('attempts >= 0', name=op.f('ck_outbox_events_attempts_non_negative')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_outbox_events'))
    )
    op.create_index('ix_outbox_events_pending_created_at', 'outbox_events', ['created_at'], unique=False, postgresql_where="status = 'pending'")
    op.create_table('processed_events',
    sa.Column('event_id', sa.Uuid(), nullable=False),
    sa.Column('consumer', sa.String(length=128), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_processed_events')),
    sa.UniqueConstraint('event_id', 'consumer', name='uq_processed_events_event_id_consumer')
    )
    op.create_table('products',
    sa.Column('sku', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=3), server_default='USD', nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('price >= 0', name=op.f('ck_products_price_non_negative')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_products')),
    sa.UniqueConstraint('sku', name=op.f('uq_products_sku'))
    )
    op.create_table('users',
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('full_name', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=32), server_default='customer', nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('customer', 'admin')", name=op.f('ck_users_role_valid')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('inventory',
    sa.Column('product_id', sa.Uuid(), nullable=False),
    sa.Column('quantity_on_hand', sa.Integer(), server_default='0', nullable=False),
    sa.Column('quantity_reserved', sa.Integer(), server_default='0', nullable=False),
    sa.Column('reorder_level', sa.Integer(), server_default='10', nullable=False),
    sa.Column('version', sa.Integer(), server_default='1', nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('quantity_on_hand >= 0', name=op.f('ck_inventory_on_hand_non_negative')),
    sa.CheckConstraint('quantity_reserved <= quantity_on_hand', name=op.f('ck_inventory_reserved_within_on_hand')),
    sa.CheckConstraint('quantity_reserved >= 0', name=op.f('ck_inventory_reserved_non_negative')),
    sa.CheckConstraint('reorder_level >= 0', name=op.f('ck_inventory_reorder_level_non_negative')),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_inventory_product_id_products'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_inventory')),
    sa.UniqueConstraint('product_id', name=op.f('uq_inventory_product_id'))
    )
    op.create_table('orders',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=32), server_default='pending', nullable=False),
    sa.Column('total_amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=3), server_default='USD', nullable=False),
    sa.Column('idempotency_key', sa.String(length=128), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('pending', 'reserved', 'paid', 'fulfilled', 'cancelled', 'failed')", name=op.f('ck_orders_status_valid')),
    sa.CheckConstraint('total_amount >= 0', name=op.f('ck_orders_total_non_negative')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_orders_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_orders')),
    sa.UniqueConstraint('idempotency_key', name=op.f('uq_orders_idempotency_key'))
    )
    op.create_index(op.f('ix_orders_status'), 'orders', ['status'], unique=False)
    op.create_index(op.f('ix_orders_user_id'), 'orders', ['user_id'], unique=False)
    op.create_table('inventory_reservations',
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('product_id', sa.Uuid(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=32), server_default='pending', nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('pending', 'confirmed', 'released', 'expired')", name=op.f('ck_inventory_reservations_status_valid')),
    sa.CheckConstraint('quantity > 0', name=op.f('ck_inventory_reservations_quantity_positive')),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_inventory_reservations_order_id_orders'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_inventory_reservations_product_id_products'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_inventory_reservations')),
    sa.UniqueConstraint('order_id', 'product_id', name='uq_inventory_reservations_order_id_product_id')
    )
    op.create_index(op.f('ix_inventory_reservations_product_id'), 'inventory_reservations', ['product_id'], unique=False)
    op.create_index('ix_inventory_reservations_status_expires_at', 'inventory_reservations', ['status', 'expires_at'], unique=False)
    op.create_table('order_items',
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('product_id', sa.Uuid(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('unit_price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('quantity > 0', name=op.f('ck_order_items_quantity_positive')),
    sa.CheckConstraint('unit_price >= 0', name=op.f('ck_order_items_unit_price_non_negative')),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_order_items_order_id_orders'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_order_items_product_id_products'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_order_items')),
    sa.UniqueConstraint('order_id', 'product_id', name='uq_order_items_order_id_product_id')
    )
    op.create_index(op.f('ix_order_items_product_id'), 'order_items', ['product_id'], unique=False)
    op.create_table('payments',
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=3), server_default='USD', nullable=False),
    sa.Column('status', sa.String(length=32), server_default='pending', nullable=False),
    sa.Column('provider', sa.String(length=32), server_default='mock', nullable=False),
    sa.Column('provider_reference', sa.String(length=128), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('pending', 'authorized', 'captured', 'failed', 'refunded')", name=op.f('ck_payments_status_valid')),
    sa.CheckConstraint('amount >= 0', name=op.f('ck_payments_amount_non_negative')),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_payments_order_id_orders'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_payments')),
    sa.UniqueConstraint('provider', 'provider_reference', name='uq_payments_provider_reference')
    )
    op.create_index(op.f('ix_payments_order_id'), 'payments', ['order_id'], unique=False)
    op.create_index(op.f('ix_payments_status'), 'payments', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_payments_status'), table_name='payments')
    op.drop_index(op.f('ix_payments_order_id'), table_name='payments')
    op.drop_table('payments')
    op.drop_index(op.f('ix_order_items_product_id'), table_name='order_items')
    op.drop_table('order_items')
    op.drop_index('ix_inventory_reservations_status_expires_at', table_name='inventory_reservations')
    op.drop_index(op.f('ix_inventory_reservations_product_id'), table_name='inventory_reservations')
    op.drop_table('inventory_reservations')
    op.drop_index(op.f('ix_orders_user_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_status'), table_name='orders')
    op.drop_table('orders')
    op.drop_table('inventory')
    op.drop_table('users')
    op.drop_table('products')
    op.drop_table('processed_events')
    op.drop_index('ix_outbox_events_pending_created_at', table_name='outbox_events', postgresql_where="status = 'pending'")
    op.drop_table('outbox_events')
