-- Jalankan sekali pada database proyek baru, sebagai pemilik skema.
BEGIN;
CREATE SCHEMA accounting;
REVOKE ALL ON SCHEMA accounting FROM PUBLIC;
SET search_path TO accounting, pg_catalog;

CREATE TABLE chart_of_accounts (
    account_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_code varchar(20) NOT NULL UNIQUE,
    account_name varchar(120) NOT NULL,
    normal_balance char(1) NOT NULL CHECK (normal_balance IN ('D','C')),
    report_class varchar(20) NOT NULL CHECK
        (report_class IN ('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE')),
    is_cash boolean NOT NULL DEFAULT false
);

CREATE TABLE journal_headers (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_date date NOT NULL,
    reference_no varchar(80) NOT NULL UNIQUE CHECK (btrim(reference_no) <> ''),
    description text NOT NULL CHECK (btrim(description) <> ''),
    voucher_type varchar(20) NOT NULL DEFAULT 'GENERAL' CHECK
        (voucher_type IN ('GENERAL','CASH_OUT','INVENTORY','REVERSAL')),
    status_posting varchar(10) NOT NULL DEFAULT 'DRAFT' CHECK
        (status_posting IN ('DRAFT','POSTED')),
    reversal_of bigint UNIQUE REFERENCES journal_headers(id) ON DELETE RESTRICT,
    created_by text NOT NULL DEFAULT session_user,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    posted_by text,
    posted_at timestamptz,
    hash_checksum varchar(64),
    CHECK ((voucher_type = 'REVERSAL') = (reversal_of IS NOT NULL)),
    CHECK (reversal_of IS NULL OR reversal_of <> id),
    CHECK ((status_posting = 'DRAFT' AND posted_by IS NULL
                AND posted_at IS NULL AND hash_checksum IS NULL)
        OR (status_posting = 'POSTED' AND posted_by IS NOT NULL
                AND posted_at IS NOT NULL AND hash_checksum ~ '^[0-9a-f]{64}$'))
);

CREATE TABLE journal_lines (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    header_id bigint NOT NULL REFERENCES journal_headers(id) ON DELETE RESTRICT,
    account_id bigint NOT NULL REFERENCES chart_of_accounts(account_id) ON DELETE RESTRICT,
    debit numeric(18,2) NOT NULL DEFAULT 0,
    credit numeric(18,2) NOT NULL DEFAULT 0,
    CHECK (debit >= 0 AND debit < 'Infinity'::numeric),
    CHECK (credit >= 0 AND credit < 'Infinity'::numeric),
    CHECK ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))
);
CREATE INDEX journal_lines_header_idx ON journal_lines(header_id);
CREATE INDEX journal_lines_account_idx ON journal_lines(account_id);

CREATE TABLE inventory_items (
    item_id varchar(10) PRIMARY KEY,
    item_name varchar(100) NOT NULL,
    stock_qty int NOT NULL DEFAULT 0 CHECK (stock_qty >= 0),
    unit_cost numeric(15,2) NOT NULL CHECK
        (unit_cost > 0 AND unit_cost < 'Infinity'::numeric)
);
CREATE TABLE inventory_transactions (
    trx_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id varchar(10) NOT NULL REFERENCES inventory_items(item_id) ON DELETE RESTRICT,
    trx_type varchar(10) NOT NULL CHECK (trx_type IN ('PURCHASE','SALE','ADJUSTMENT')),
    qty int NOT NULL,
    trx_date timestamptz NOT NULL DEFAULT clock_timestamp(),
    reference_no varchar(80) NOT NULL UNIQUE CHECK (btrim(reference_no) <> ''),
    reason text NOT NULL CHECK (btrim(reason) <> ''),
    created_by text NOT NULL DEFAULT session_user,
    unit_cost_snapshot numeric(15,2) NOT NULL,
    journal_id bigint NOT NULL UNIQUE REFERENCES journal_headers(id) ON DELETE RESTRICT,
    CHECK ((trx_type IN ('PURCHASE','SALE') AND qty > 0)
        OR (trx_type = 'ADJUSTMENT' AND qty <> 0))
);

CREATE TABLE audit_log (
    audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    actor text NOT NULL DEFAULT session_user,
    table_name text NOT NULL,
    operation text NOT NULL,
    row_key text NOT NULL,
    old_data jsonb,
    new_data jsonb,
    transaction_id bigint NOT NULL DEFAULT txid_current()
);
COMMIT;
