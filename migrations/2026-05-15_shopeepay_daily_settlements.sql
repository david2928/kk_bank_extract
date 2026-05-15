-- 2026-05-15: P4-SHOPEEPAY epic.
-- Create finance.shopeepay_daily_settlements to ingest the authoritative
-- per-day settlement summary email from support_th@shopeepay.com. T+1 net
-- deposit to KBank Savings 170-3-27029-4 equals net_amount.
--
-- Idempotency: settlement_date is UNIQUE. Loader uses upsert on conflict so
-- duplicate-resend emails (observed on 2026-04-30) are no-ops.
-- source_message_id is the last Gmail message_id that wrote the row (audit).

CREATE TABLE IF NOT EXISTS finance.shopeepay_daily_settlements (
  id                       BIGSERIAL PRIMARY KEY,
  settlement_date          DATE          NOT NULL UNIQUE,
  gross_amount             NUMERIC(12,2) NOT NULL,
  refund_amount            NUMERIC(12,2) NOT NULL DEFAULT 0,
  merchant_support_amount  NUMERIC(12,2) NOT NULL DEFAULT 0,
  commission_amount        NUMERIC(12,2) NOT NULL,
  vat_on_commission        NUMERIC(12,2) NOT NULL,
  wht_amount               NUMERIC(12,2) NOT NULL,
  rollover_amount          NUMERIC(12,2) NOT NULL DEFAULT 0,
  net_amount               NUMERIC(12,2) NOT NULL,
  bank_account_tail        TEXT          NOT NULL CHECK (bank_account_tail ~ '^\d{4}$'),
  source_message_id        TEXT          NOT NULL,
  gdrive_file_id           TEXT,
  tax_invoice_no           TEXT,
  raw_body                 TEXT          NOT NULL,
  created_at               TIMESTAMPTZ   NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_shopeepay_settlement_date
  ON finance.shopeepay_daily_settlements (settlement_date);

COMMENT ON TABLE  finance.shopeepay_daily_settlements IS
  'ShopeePay daily settlement summary, ingested from support_th@shopeepay.com emails. T+1 net deposit to KBank Savings 170-3-27029-4 equals net_amount on transaction_date = settlement_date + 1 day. Empirical formula: net = gross - refund + merchant_support - commission - vat_on_commission + rollover. WHT is informational (tax reporting), NOT subtracted from the deposit.';
COMMENT ON COLUMN finance.shopeepay_daily_settlements.settlement_date IS
  'The single calendar day this settlement covers (UNIQUE — one row per day; duplicate-resend emails upsert).';
COMMENT ON COLUMN finance.shopeepay_daily_settlements.source_message_id IS
  'Most recent Gmail message_id that wrote this row. For audit; the canonical dedup happens via UNIQUE(settlement_date) + Gmail label.';
COMMENT ON COLUMN finance.shopeepay_daily_settlements.tax_invoice_no IS
  'Reserved for a future monthly tax-invoice PDF backfill, analogous to EWALLET E-TAX flow. NULL at ingestion time.';
