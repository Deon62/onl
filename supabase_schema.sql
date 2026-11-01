BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE TABLE expenses (
    id UUID NOT NULL, 
    category VARCHAR(60) NOT NULL, 
    description VARCHAR(255) NOT NULL, 
    amount_cents BIGINT NOT NULL, 
    provider VARCHAR(120) NOT NULL, 
    date DATE NOT NULL, 
    status VARCHAR(10) NOT NULL, 
    created_by VARCHAR(254) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_expenses PRIMARY KEY (id), 
    CONSTRAINT ck_expenses_status_valid CHECK (status IN ('Paid', 'Pending', 'Overdue'))
);

CREATE INDEX ix_expenses_category ON expenses (category);

CREATE INDEX ix_expenses_date ON expenses (date);

CREATE TABLE merchants (
    id UUID NOT NULL, 
    code VARCHAR(16) NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    legal_name VARCHAR(200) NOT NULL, 
    email VARCHAR(254) NOT NULL, 
    phone VARCHAR(16) NOT NULL, 
    contact_name VARCHAR(120) NOT NULL, 
    industry VARCHAR(80) NOT NULL, 
    location VARCHAR(120) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    reference_prefix VARCHAR(3) NOT NULL, 
    pricing_percent_bps INTEGER NOT NULL, 
    pricing_fixed_cents BIGINT NOT NULL, 
    pricing_min_cents BIGINT NOT NULL, 
    pricing_max_cents BIGINT NOT NULL, 
    payout_schedule VARCHAR(10) NOT NULL, 
    payout_method VARCHAR(20) NOT NULL, 
    payout_destination VARCHAR(120) NOT NULL, 
    settlement JSONB NOT NULL, 
    sms_alerts JSONB NOT NULL, 
    subscription VARCHAR(40) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_merchants PRIMARY KEY (id), 
    CONSTRAINT ck_merchants_payout_method_valid CHECK (payout_method IN ('M-Pesa', 'Till', 'Paybill', 'Bank transfer')), 
    CONSTRAINT ck_merchants_payout_schedule_valid CHECK (payout_schedule IN ('Manual', 'Daily', 'Weekly', 'Monthly')), 
    CONSTRAINT ck_merchants_status_valid CHECK (status IN ('Pending Review', 'Active', 'Suspended')), 
    CONSTRAINT uq_merchants_code UNIQUE (code), 
    CONSTRAINT uq_merchants_email UNIQUE (email), 
    CONSTRAINT uq_merchants_reference_prefix UNIQUE (reference_prefix)
);

CREATE TABLE notifications (
    id UUID NOT NULL, 
    audience VARCHAR(40) NOT NULL, 
    title VARCHAR(120) NOT NULL, 
    body VARCHAR(500) NOT NULL, 
    read BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_notifications PRIMARY KEY (id)
);

CREATE INDEX ix_notifications_audience_created ON notifications (audience, created_at);

CREATE TABLE platform_config (
    key VARCHAR(60) NOT NULL, 
    value JSONB NOT NULL, 
    updated_by VARCHAR(254) NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_platform_config PRIMARY KEY (key)
);

CREATE TABLE access_requests (
    id UUID NOT NULL, 
    business VARCHAR(120) NOT NULL, 
    contact_name VARCHAR(120) NOT NULL, 
    email VARCHAR(254) NOT NULL, 
    phone VARCHAR(16) NOT NULL, 
    volume VARCHAR(40) NOT NULL, 
    message TEXT NOT NULL, 
    status VARCHAR(10) NOT NULL, 
    documents JSONB NOT NULL, 
    merchant_id UUID, 
    reviewed_by VARCHAR(254), 
    reviewed_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_access_requests PRIMARY KEY (id), 
    CONSTRAINT ck_access_requests_status_valid CHECK (status IN ('New', 'Approved', 'Rejected')), 
    CONSTRAINT fk_access_requests_merchant_id_merchants FOREIGN KEY(merchant_id) REFERENCES merchants (id) ON DELETE SET NULL
);

CREATE INDEX ix_access_requests_email ON access_requests (email);

CREATE TABLE activity_log (
    id UUID NOT NULL, 
    actor VARCHAR(254) NOT NULL, 
    role VARCHAR(20) NOT NULL, 
    action VARCHAR(255) NOT NULL, 
    target VARCHAR(255) NOT NULL, 
    merchant_id UUID, 
    ip VARCHAR(45), 
    at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_activity_log PRIMARY KEY (id), 
    CONSTRAINT fk_activity_log_merchant_id_merchants FOREIGN KEY(merchant_id) REFERENCES merchants (id) ON DELETE SET NULL
);

CREATE INDEX ix_activity_merchant_at ON activity_log (merchant_id, at);

CREATE TABLE api_keys (
    id UUID NOT NULL, 
    merchant_id UUID NOT NULL, 
    kind VARCHAR(12) NOT NULL, 
    label VARCHAR(80) NOT NULL, 
    prefix VARCHAR(24) NOT NULL, 
    key_hash VARCHAR(64) NOT NULL, 
    created_by VARCHAR(254) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    last_used_at TIMESTAMP WITH TIME ZONE, 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_api_keys PRIMARY KEY (id), 
    CONSTRAINT ck_api_keys_kind_valid CHECK (kind IN ('secret', 'publishable')), 
    CONSTRAINT fk_api_keys_merchant_id_merchants FOREIGN KEY(merchant_id) REFERENCES merchants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_api_keys_key_hash UNIQUE (key_hash)
);

CREATE INDEX ix_api_keys_merchant_id ON api_keys (merchant_id);

CREATE TABLE merchant_domains (
    id UUID NOT NULL, 
    merchant_id UUID NOT NULL, 
    domain VARCHAR(253) NOT NULL, 
    verified_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_merchant_domains PRIMARY KEY (id), 
    CONSTRAINT fk_merchant_domains_merchant_id_merchants FOREIGN KEY(merchant_id) REFERENCES merchants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_merchant_domains_domain UNIQUE (domain)
);

CREATE INDEX ix_merchant_domains_merchant_id ON merchant_domains (merchant_id);

CREATE TABLE payments (
    id UUID NOT NULL, 
    merchant_id UUID, 
    reference VARCHAR(12) NOT NULL, 
    idempotency_key VARCHAR(80), 
    checkout_request_id VARCHAR(80), 
    merchant_request_id VARCHAR(80), 
    mpesa_receipt VARCHAR(20), 
    amount_cents BIGINT NOT NULL, 
    phone VARCHAR(16) NOT NULL, 
    customer_name VARCHAR(120) NOT NULL, 
    description VARCHAR(120) NOT NULL, 
    order_ref VARCHAR(80) NOT NULL, 
    domain VARCHAR(253), 
    channel VARCHAR(16) NOT NULL, 
    status VARCHAR(12) NOT NULL, 
    attribution VARCHAR(10) NOT NULL, 
    fee_cents BIGINT NOT NULL, 
    provider_charge_cents BIGINT NOT NULL, 
    sms_fee_cents BIGINT NOT NULL, 
    sms_cost_cents BIGINT NOT NULL, 
    result_code INTEGER, 
    result_desc VARCHAR(255), 
    initiated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    confirmed_at TIMESTAMP WITH TIME ZONE, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_payments PRIMARY KEY (id), 
    CONSTRAINT ck_payments_attribution_valid CHECK (attribution IN ('Matched', 'Unmatched', 'Manual')), 
    CONSTRAINT ck_payments_channel_valid CHECK (channel IN ('STK Push', 'Payment Link', 'Till')), 
    CONSTRAINT ck_payments_status_valid CHECK (status IN ('Initiated', 'Pending', 'Successful', 'Failed', 'Cancelled', 'Reversed', 'Refunded', 'Unmatched')), 
    CONSTRAINT fk_payments_merchant_id_merchants FOREIGN KEY(merchant_id) REFERENCES merchants (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_payments_checkout_request_id UNIQUE (checkout_request_id), 
    CONSTRAINT uq_payments_merchant_idempotency UNIQUE (merchant_id, idempotency_key), 
    CONSTRAINT uq_payments_mpesa_receipt UNIQUE (mpesa_receipt), 
    CONSTRAINT uq_payments_reference UNIQUE (reference)
);

CREATE INDEX ix_payments_merchant_initiated ON payments (merchant_id, initiated_at);

CREATE INDEX ix_payments_status_initiated ON payments (status, initiated_at);

CREATE TABLE payouts (
    id UUID NOT NULL, 
    reference VARCHAR(24) NOT NULL, 
    merchant_id UUID NOT NULL, 
    amount_cents BIGINT NOT NULL, 
    fee_cents BIGINT NOT NULL, 
    net_cents BIGINT NOT NULL, 
    provider_cost_cents BIGINT NOT NULL, 
    method VARCHAR(20) NOT NULL, 
    destination VARCHAR(120) NOT NULL, 
    remittance VARCHAR(8), 
    status VARCHAR(12) NOT NULL, 
    initiated_by VARCHAR(10) NOT NULL, 
    provider_ref VARCHAR(80), 
    failure_reason VARCHAR(255), 
    approved_by VARCHAR(254), 
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_payouts PRIMARY KEY (id), 
    CONSTRAINT ck_payouts_initiated_by_valid CHECK (initiated_by IN ('Merchant', 'Scheduled', 'Admin')), 
    CONSTRAINT ck_payouts_method_valid CHECK (method IN ('M-Pesa', 'Till', 'Paybill', 'Bank transfer')), 
    CONSTRAINT ck_payouts_remittance_valid CHECK (remittance IS NULL OR remittance IN ('B2C', 'B2B', 'Manual')), 
    CONSTRAINT ck_payouts_status_valid CHECK (status IN ('Pending', 'Processing', 'Completed', 'Failed')), 
    CONSTRAINT fk_payouts_merchant_id_merchants FOREIGN KEY(merchant_id) REFERENCES merchants (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_payouts_reference UNIQUE (reference)
);

CREATE INDEX ix_payouts_merchant_id ON payouts (merchant_id);

CREATE TABLE profiles (
    user_id UUID NOT NULL, 
    email VARCHAR(254) NOT NULL, 
    full_name VARCHAR(120) NOT NULL, 
    role VARCHAR(20) NOT NULL, 
    merchant_id UUID, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_profiles PRIMARY KEY (user_id), 
    CONSTRAINT ck_profiles_role_valid CHECK (role IN ('super_admin', 'ops', 'finance', 'merchant_owner', 'merchant_staff')), 
    CONSTRAINT fk_profiles_merchant_id_merchants FOREIGN KEY(merchant_id) REFERENCES merchants (id) ON DELETE CASCADE, 
    CONSTRAINT uq_profiles_email UNIQUE (email)
);

CREATE INDEX ix_profiles_merchant_id ON profiles (merchant_id);

CREATE TABLE revenue_entries (
    id UUID NOT NULL, 
    merchant_id UUID, 
    source VARCHAR(40) NOT NULL, 
    description VARCHAR(255) NOT NULL, 
    amount_cents BIGINT NOT NULL, 
    date DATE NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_revenue_entries PRIMARY KEY (id), 
    CONSTRAINT fk_revenue_entries_merchant_id_merchants FOREIGN KEY(merchant_id) REFERENCES merchants (id) ON DELETE SET NULL
);

CREATE INDEX ix_revenue_entries_date ON revenue_entries (date);

CREATE INDEX ix_revenue_entries_merchant_id ON revenue_entries (merchant_id);

CREATE TABLE sms_topups (
    id UUID NOT NULL, 
    merchant_id UUID NOT NULL, 
    amount_cents BIGINT NOT NULL, 
    method VARCHAR(10) NOT NULL, 
    reference VARCHAR(24) NOT NULL, 
    mpesa_receipt VARCHAR(20), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_sms_topups PRIMARY KEY (id), 
    CONSTRAINT fk_sms_topups_merchant_id_merchants FOREIGN KEY(merchant_id) REFERENCES merchants (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_sms_topups_mpesa_receipt UNIQUE (mpesa_receipt), 
    CONSTRAINT uq_sms_topups_reference UNIQUE (reference)
);

CREATE INDEX ix_sms_topups_merchant_id ON sms_topups (merchant_id);

CREATE TABLE callbacks (
    id UUID NOT NULL, 
    kind VARCHAR(20) NOT NULL, 
    payload JSONB NOT NULL, 
    source_ip VARCHAR(45), 
    received_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    processed_at TIMESTAMP WITH TIME ZONE, 
    payment_id UUID, 
    error TEXT, 
    CONSTRAINT pk_callbacks PRIMARY KEY (id), 
    CONSTRAINT ck_callbacks_kind_valid CHECK (kind IN ('stk', 'c2b_validation', 'c2b_confirmation', 'b2c', 'b2b', 'timeout')), 
    CONSTRAINT fk_callbacks_payment_id_payments FOREIGN KEY(payment_id) REFERENCES payments (id) ON DELETE SET NULL
);

CREATE INDEX ix_callbacks_kind ON callbacks (kind);

CREATE TABLE ledger_entries (
    id UUID NOT NULL, 
    merchant_id UUID NOT NULL, 
    kind VARCHAR(20) NOT NULL, 
    amount_cents BIGINT NOT NULL, 
    payment_id UUID, 
    payout_id UUID, 
    sms_topup_id UUID, 
    available_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    memo VARCHAR(255) NOT NULL, 
    created_by VARCHAR(254) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_ledger_entries PRIMARY KEY (id), 
    CONSTRAINT ck_ledger_entries_kind_valid CHECK (kind IN ('collection', 'fee', 'refund', 'fee_reversal', 'payout', 'payout_fee', 'payout_reversal', 'sms_topup', 'adjustment')), 
    CONSTRAINT fk_ledger_entries_merchant_id_merchants FOREIGN KEY(merchant_id) REFERENCES merchants (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_ledger_entries_payment_id_payments FOREIGN KEY(payment_id) REFERENCES payments (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_ledger_entries_payout_id_payouts FOREIGN KEY(payout_id) REFERENCES payouts (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_ledger_entries_sms_topup_id_sms_topups FOREIGN KEY(sms_topup_id) REFERENCES sms_topups (id) ON DELETE RESTRICT
);

CREATE INDEX ix_ledger_entries_payment_id ON ledger_entries (payment_id);

CREATE INDEX ix_ledger_entries_payout_id ON ledger_entries (payout_id);

CREATE INDEX ix_ledger_merchant_available ON ledger_entries (merchant_id, available_at);

ALTER TABLE expenses ENABLE ROW LEVEL SECURITY;

ALTER TABLE merchants ENABLE ROW LEVEL SECURITY;

ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

ALTER TABLE platform_config ENABLE ROW LEVEL SECURITY;

ALTER TABLE access_requests ENABLE ROW LEVEL SECURITY;

ALTER TABLE activity_log ENABLE ROW LEVEL SECURITY;

ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;

ALTER TABLE merchant_domains ENABLE ROW LEVEL SECURITY;

ALTER TABLE payments ENABLE ROW LEVEL SECURITY;

ALTER TABLE payouts ENABLE ROW LEVEL SECURITY;

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

ALTER TABLE revenue_entries ENABLE ROW LEVEL SECURITY;

ALTER TABLE sms_topups ENABLE ROW LEVEL SECURITY;

ALTER TABLE callbacks ENABLE ROW LEVEL SECURITY;

ALTER TABLE ledger_entries ENABLE ROW LEVEL SECURITY;

ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY;

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

COMMIT;

