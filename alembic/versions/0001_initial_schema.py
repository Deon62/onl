"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-01

All tables for phase 1. Row Level Security is enabled on every table with no policies: Supabase exposes the
public schema through its REST API (anon / authenticated keys), and RLS-without-policies makes these tables
unreachable that way. Only the backend's database role (which bypasses RLS) can read or write them.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ['expenses', 'merchants', 'notifications', 'platform_config', 'access_requests', 'activity_log', 'api_keys', 'merchant_domains', 'payments', 'payouts', 'profiles', 'revenue_entries', 'sms_topups', 'callbacks', 'ledger_entries']


def upgrade() -> None:
    op.create_table('expenses',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('category', sa.String(length=60), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=False),
    sa.Column('amount_cents', sa.BigInteger(), nullable=False),
    sa.Column('provider', sa.String(length=120), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('created_by', sa.String(length=254), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("status IN ('Paid', 'Pending', 'Overdue')", name=op.f('ck_expenses_status_valid')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_expenses'))
    )
    op.create_index(op.f('ix_expenses_category'), 'expenses', ['category'], unique=False)
    op.create_index(op.f('ix_expenses_date'), 'expenses', ['date'], unique=False)
    op.create_table('merchants',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=16), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('legal_name', sa.String(length=200), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('phone', sa.String(length=16), nullable=False),
    sa.Column('contact_name', sa.String(length=120), nullable=False),
    sa.Column('industry', sa.String(length=80), nullable=False),
    sa.Column('location', sa.String(length=120), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('reference_prefix', sa.String(length=3), nullable=False),
    sa.Column('pricing_percent_bps', sa.Integer(), nullable=False),
    sa.Column('pricing_fixed_cents', sa.BigInteger(), nullable=False),
    sa.Column('pricing_min_cents', sa.BigInteger(), nullable=False),
    sa.Column('pricing_max_cents', sa.BigInteger(), nullable=False),
    sa.Column('payout_schedule', sa.String(length=10), nullable=False),
    sa.Column('payout_method', sa.String(length=20), nullable=False),
    sa.Column('payout_destination', sa.String(length=120), nullable=False),
    sa.Column('settlement', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('sms_alerts', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('subscription', sa.String(length=40), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("payout_method IN ('M-Pesa', 'Till', 'Paybill', 'Bank transfer')", name=op.f('ck_merchants_payout_method_valid')),
    sa.CheckConstraint("payout_schedule IN ('Manual', 'Daily', 'Weekly', 'Monthly')", name=op.f('ck_merchants_payout_schedule_valid')),
    sa.CheckConstraint("status IN ('Pending Review', 'Active', 'Suspended')", name=op.f('ck_merchants_status_valid')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_merchants')),
    sa.UniqueConstraint('code', name=op.f('uq_merchants_code')),
    sa.UniqueConstraint('email', name=op.f('uq_merchants_email')),
    sa.UniqueConstraint('reference_prefix', name=op.f('uq_merchants_reference_prefix'))
    )
    op.create_table('notifications',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('audience', sa.String(length=40), nullable=False),
    sa.Column('title', sa.String(length=120), nullable=False),
    sa.Column('body', sa.String(length=500), nullable=False),
    sa.Column('read', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications'))
    )
    op.create_index('ix_notifications_audience_created', 'notifications', ['audience', 'created_at'], unique=False)
    op.create_table('platform_config',
    sa.Column('key', sa.String(length=60), nullable=False),
    sa.Column('value', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('updated_by', sa.String(length=254), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('key', name=op.f('pk_platform_config'))
    )
    op.create_table('access_requests',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('business', sa.String(length=120), nullable=False),
    sa.Column('contact_name', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('phone', sa.String(length=16), nullable=False),
    sa.Column('volume', sa.String(length=40), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('documents', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('merchant_id', sa.Uuid(), nullable=True),
    sa.Column('reviewed_by', sa.String(length=254), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("status IN ('New', 'Approved', 'Rejected')", name=op.f('ck_access_requests_status_valid')),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], name=op.f('fk_access_requests_merchant_id_merchants'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_access_requests'))
    )
    op.create_index(op.f('ix_access_requests_email'), 'access_requests', ['email'], unique=False)
    op.create_table('activity_log',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('actor', sa.String(length=254), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('action', sa.String(length=255), nullable=False),
    sa.Column('target', sa.String(length=255), nullable=False),
    sa.Column('merchant_id', sa.Uuid(), nullable=True),
    sa.Column('ip', sa.String(length=45), nullable=True),
    sa.Column('at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], name=op.f('fk_activity_log_merchant_id_merchants'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_activity_log'))
    )
    op.create_index('ix_activity_merchant_at', 'activity_log', ['merchant_id', 'at'], unique=False)
    op.create_table('api_keys',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('merchant_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=12), nullable=False),
    sa.Column('label', sa.String(length=80), nullable=False),
    sa.Column('prefix', sa.String(length=24), nullable=False),
    sa.Column('key_hash', sa.String(length=64), nullable=False),
    sa.Column('created_by', sa.String(length=254), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("kind IN ('secret', 'publishable')", name=op.f('ck_api_keys_kind_valid')),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], name=op.f('fk_api_keys_merchant_id_merchants'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_api_keys')),
    sa.UniqueConstraint('key_hash', name=op.f('uq_api_keys_key_hash'))
    )
    op.create_index(op.f('ix_api_keys_merchant_id'), 'api_keys', ['merchant_id'], unique=False)
    op.create_table('merchant_domains',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('merchant_id', sa.Uuid(), nullable=False),
    sa.Column('domain', sa.String(length=253), nullable=False),
    sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], name=op.f('fk_merchant_domains_merchant_id_merchants'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_merchant_domains')),
    sa.UniqueConstraint('domain', name=op.f('uq_merchant_domains_domain'))
    )
    op.create_index(op.f('ix_merchant_domains_merchant_id'), 'merchant_domains', ['merchant_id'], unique=False)
    op.create_table('payments',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('merchant_id', sa.Uuid(), nullable=True),
    sa.Column('reference', sa.String(length=12), nullable=False),
    sa.Column('idempotency_key', sa.String(length=80), nullable=True),
    sa.Column('checkout_request_id', sa.String(length=80), nullable=True),
    sa.Column('merchant_request_id', sa.String(length=80), nullable=True),
    sa.Column('mpesa_receipt', sa.String(length=20), nullable=True),
    sa.Column('amount_cents', sa.BigInteger(), nullable=False),
    sa.Column('phone', sa.String(length=16), nullable=False),
    sa.Column('customer_name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.String(length=120), nullable=False),
    sa.Column('order_ref', sa.String(length=80), nullable=False),
    sa.Column('domain', sa.String(length=253), nullable=True),
    sa.Column('channel', sa.String(length=16), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('attribution', sa.String(length=10), nullable=False),
    sa.Column('fee_cents', sa.BigInteger(), nullable=False),
    sa.Column('provider_charge_cents', sa.BigInteger(), nullable=False),
    sa.Column('sms_fee_cents', sa.BigInteger(), nullable=False),
    sa.Column('sms_cost_cents', sa.BigInteger(), nullable=False),
    sa.Column('result_code', sa.Integer(), nullable=True),
    sa.Column('result_desc', sa.String(length=255), nullable=True),
    sa.Column('initiated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("attribution IN ('Matched', 'Unmatched', 'Manual')", name=op.f('ck_payments_attribution_valid')),
    sa.CheckConstraint("channel IN ('STK Push', 'Payment Link', 'Till')", name=op.f('ck_payments_channel_valid')),
    sa.CheckConstraint("status IN ('Initiated', 'Pending', 'Successful', 'Failed', 'Cancelled', 'Reversed', 'Refunded', 'Unmatched')", name=op.f('ck_payments_status_valid')),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], name=op.f('fk_payments_merchant_id_merchants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_payments')),
    sa.UniqueConstraint('checkout_request_id', name=op.f('uq_payments_checkout_request_id')),
    sa.UniqueConstraint('merchant_id', 'idempotency_key', name='uq_payments_merchant_idempotency'),
    sa.UniqueConstraint('mpesa_receipt', name=op.f('uq_payments_mpesa_receipt')),
    sa.UniqueConstraint('reference', name=op.f('uq_payments_reference'))
    )
    op.create_index('ix_payments_merchant_initiated', 'payments', ['merchant_id', 'initiated_at'], unique=False)
    op.create_index('ix_payments_status_initiated', 'payments', ['status', 'initiated_at'], unique=False)
    op.create_table('payouts',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('reference', sa.String(length=24), nullable=False),
    sa.Column('merchant_id', sa.Uuid(), nullable=False),
    sa.Column('amount_cents', sa.BigInteger(), nullable=False),
    sa.Column('fee_cents', sa.BigInteger(), nullable=False),
    sa.Column('net_cents', sa.BigInteger(), nullable=False),
    sa.Column('provider_cost_cents', sa.BigInteger(), nullable=False),
    sa.Column('method', sa.String(length=20), nullable=False),
    sa.Column('destination', sa.String(length=120), nullable=False),
    sa.Column('remittance', sa.String(length=8), nullable=True),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('initiated_by', sa.String(length=10), nullable=False),
    sa.Column('provider_ref', sa.String(length=80), nullable=True),
    sa.Column('failure_reason', sa.String(length=255), nullable=True),
    sa.Column('approved_by', sa.String(length=254), nullable=True),
    sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("initiated_by IN ('Merchant', 'Scheduled', 'Admin')", name=op.f('ck_payouts_initiated_by_valid')),
    sa.CheckConstraint("method IN ('M-Pesa', 'Till', 'Paybill', 'Bank transfer')", name=op.f('ck_payouts_method_valid')),
    sa.CheckConstraint("remittance IS NULL OR remittance IN ('B2C', 'B2B', 'Manual')", name=op.f('ck_payouts_remittance_valid')),
    sa.CheckConstraint("status IN ('Pending', 'Processing', 'Completed', 'Failed')", name=op.f('ck_payouts_status_valid')),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], name=op.f('fk_payouts_merchant_id_merchants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_payouts')),
    sa.UniqueConstraint('reference', name=op.f('uq_payouts_reference'))
    )
    op.create_index(op.f('ix_payouts_merchant_id'), 'payouts', ['merchant_id'], unique=False)
    op.create_table('profiles',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('full_name', sa.String(length=120), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('merchant_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("role IN ('super_admin', 'ops', 'finance', 'merchant_owner', 'merchant_staff')", name=op.f('ck_profiles_role_valid')),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], name=op.f('fk_profiles_merchant_id_merchants'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_profiles')),
    sa.UniqueConstraint('email', name=op.f('uq_profiles_email'))
    )
    op.create_index(op.f('ix_profiles_merchant_id'), 'profiles', ['merchant_id'], unique=False)
    op.create_table('revenue_entries',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('merchant_id', sa.Uuid(), nullable=True),
    sa.Column('source', sa.String(length=40), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=False),
    sa.Column('amount_cents', sa.BigInteger(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], name=op.f('fk_revenue_entries_merchant_id_merchants'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_revenue_entries'))
    )
    op.create_index(op.f('ix_revenue_entries_date'), 'revenue_entries', ['date'], unique=False)
    op.create_index(op.f('ix_revenue_entries_merchant_id'), 'revenue_entries', ['merchant_id'], unique=False)
    op.create_table('sms_topups',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('merchant_id', sa.Uuid(), nullable=False),
    sa.Column('amount_cents', sa.BigInteger(), nullable=False),
    sa.Column('method', sa.String(length=10), nullable=False),
    sa.Column('reference', sa.String(length=24), nullable=False),
    sa.Column('mpesa_receipt', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], name=op.f('fk_sms_topups_merchant_id_merchants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sms_topups')),
    sa.UniqueConstraint('mpesa_receipt', name=op.f('uq_sms_topups_mpesa_receipt')),
    sa.UniqueConstraint('reference', name=op.f('uq_sms_topups_reference'))
    )
    op.create_index(op.f('ix_sms_topups_merchant_id'), 'sms_topups', ['merchant_id'], unique=False)
    op.create_table('callbacks',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('payload', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('source_ip', sa.String(length=45), nullable=True),
    sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('payment_id', sa.Uuid(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.CheckConstraint("kind IN ('stk', 'c2b_validation', 'c2b_confirmation', 'b2c', 'b2b', 'timeout')", name=op.f('ck_callbacks_kind_valid')),
    sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], name=op.f('fk_callbacks_payment_id_payments'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_callbacks'))
    )
    op.create_index(op.f('ix_callbacks_kind'), 'callbacks', ['kind'], unique=False)
    op.create_table('ledger_entries',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('merchant_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('amount_cents', sa.BigInteger(), nullable=False),
    sa.Column('payment_id', sa.Uuid(), nullable=True),
    sa.Column('payout_id', sa.Uuid(), nullable=True),
    sa.Column('sms_topup_id', sa.Uuid(), nullable=True),
    sa.Column('available_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('memo', sa.String(length=255), nullable=False),
    sa.Column('created_by', sa.String(length=254), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("kind IN ('collection', 'fee', 'refund', 'fee_reversal', 'payout', 'payout_fee', 'payout_reversal', 'sms_topup', 'adjustment')", name=op.f('ck_ledger_entries_kind_valid')),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], name=op.f('fk_ledger_entries_merchant_id_merchants'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], name=op.f('fk_ledger_entries_payment_id_payments'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['payout_id'], ['payouts.id'], name=op.f('fk_ledger_entries_payout_id_payouts'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['sms_topup_id'], ['sms_topups.id'], name=op.f('fk_ledger_entries_sms_topup_id_sms_topups'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ledger_entries'))
    )
    op.create_index(op.f('ix_ledger_entries_payment_id'), 'ledger_entries', ['payment_id'], unique=False)
    op.create_index(op.f('ix_ledger_entries_payout_id'), 'ledger_entries', ['payout_id'], unique=False)
    op.create_index('ix_ledger_merchant_available', 'ledger_entries', ['merchant_id', 'available_at'], unique=False)

    if op.get_bind().dialect.name == "postgresql":
        for table in [*TABLES, "alembic_version"]:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index(op.f('ix_ledger_entries_payment_id'), table_name='ledger_entries')
    op.drop_index(op.f('ix_ledger_entries_payout_id'), table_name='ledger_entries')
    op.drop_index('ix_ledger_merchant_available', table_name='ledger_entries')
    op.drop_table('ledger_entries')
    op.drop_index(op.f('ix_callbacks_kind'), table_name='callbacks')
    op.drop_table('callbacks')
    op.drop_index(op.f('ix_sms_topups_merchant_id'), table_name='sms_topups')
    op.drop_table('sms_topups')
    op.drop_index(op.f('ix_revenue_entries_date'), table_name='revenue_entries')
    op.drop_index(op.f('ix_revenue_entries_merchant_id'), table_name='revenue_entries')
    op.drop_table('revenue_entries')
    op.drop_index(op.f('ix_profiles_merchant_id'), table_name='profiles')
    op.drop_table('profiles')
    op.drop_index(op.f('ix_payouts_merchant_id'), table_name='payouts')
    op.drop_table('payouts')
    op.drop_index('ix_payments_merchant_initiated', table_name='payments')
    op.drop_index('ix_payments_status_initiated', table_name='payments')
    op.drop_table('payments')
    op.drop_index(op.f('ix_merchant_domains_merchant_id'), table_name='merchant_domains')
    op.drop_table('merchant_domains')
    op.drop_index(op.f('ix_api_keys_merchant_id'), table_name='api_keys')
    op.drop_table('api_keys')
    op.drop_index('ix_activity_merchant_at', table_name='activity_log')
    op.drop_table('activity_log')
    op.drop_index(op.f('ix_access_requests_email'), table_name='access_requests')
    op.drop_table('access_requests')
    op.drop_table('platform_config')
    op.drop_index('ix_notifications_audience_created', table_name='notifications')
    op.drop_table('notifications')
    op.drop_table('merchants')
    op.drop_index(op.f('ix_expenses_category'), table_name='expenses')
    op.drop_index(op.f('ix_expenses_date'), table_name='expenses')
    op.drop_table('expenses')
