-- Adapter Data API: aplikasi cukup memakai Project URL + anon key.
-- Tabel accounting tetap tidak dapat ditulis langsung; perubahan hanya lewat RPC tervalidasi.
BEGIN;

CREATE OR REPLACE FUNCTION public.uts_accounts() RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, accounting AS $$
  SELECT COALESCE(jsonb_agg(to_jsonb(a) ORDER BY a.account_code), '[]'::jsonb)
  FROM accounting.chart_of_accounts a
$$;

CREATE OR REPLACE FUNCTION public.uts_items() RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, accounting AS $$
  SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.item_id), '[]'::jsonb)
  FROM (
    SELECT i.*, i.stock_qty*i.unit_cost AS stock_value
    FROM accounting.inventory_items i
  ) x
$$;

CREATE OR REPLACE FUNCTION public.uts_journals() RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, accounting AS $$
  SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.id DESC), '[]'::jsonb)
  FROM (
    SELECT h.id,h.transaction_date,h.reference_no,h.description,h.voucher_type,
      h.status_posting,h.reversal_of,h.created_by,h.created_at,h.hash_checksum,
      (SELECT sum(l.debit) FROM accounting.journal_lines l WHERE l.header_id=h.id) AS amount,
      accounting.verify_journal(h.id) AS checksum_valid
    FROM accounting.journal_headers h
    WHERE h.status_posting='POSTED' ORDER BY h.id DESC LIMIT 200
  ) x
$$;

CREATE OR REPLACE FUNCTION public.uts_journal_lines(p_header_id bigint) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, accounting AS $$
  SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.id), '[]'::jsonb)
  FROM (
    SELECT l.id,a.account_code,a.account_name,l.debit,l.credit
    FROM accounting.journal_lines l
    JOIN accounting.chart_of_accounts a USING(account_id)
    WHERE l.header_id=p_header_id
  ) x
$$;

CREATE OR REPLACE FUNCTION public.uts_audit() RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, accounting AS $$
  SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.audit_id DESC), '[]'::jsonb)
  FROM (SELECT * FROM accounting.audit_log ORDER BY audit_id DESC LIMIT 200) x
$$;

CREATE OR REPLACE FUNCTION public.uts_submit_cash_voucher(
  p_date date,p_ref text,p_desc text,p_lines jsonb) RETURNS bigint
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, accounting AS $$
  SELECT accounting.submit_cash_voucher(p_date,p_ref,p_desc,p_lines)
$$;

CREATE OR REPLACE FUNCTION public.uts_record_inventory(
  p_item text,p_type text,p_qty int,p_ref text,p_reason text) RETURNS bigint
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, accounting AS $$
  SELECT accounting.record_inventory(p_item,p_type,p_qty,p_ref,p_reason)
$$;

CREATE OR REPLACE FUNCTION public.uts_reverse_journal(
  p_id bigint,p_date date,p_ref text,p_reason text) RETURNS bigint
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, accounting AS $$
  SELECT accounting.reverse_journal(p_id,p_date,p_ref,p_reason)
$$;

REVOKE ALL ON FUNCTION public.uts_accounts(), public.uts_items(),
 public.uts_journals(), public.uts_journal_lines(bigint), public.uts_audit(),
 public.uts_submit_cash_voucher(date,text,text,jsonb),
 public.uts_record_inventory(text,text,int,text,text),
 public.uts_reverse_journal(bigint,date,text,text) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.uts_accounts(), public.uts_items(),
 public.uts_journals(), public.uts_journal_lines(bigint), public.uts_audit(),
 public.uts_submit_cash_voucher(date,text,text,jsonb),
 public.uts_record_inventory(text,text,int,text,text),
 public.uts_reverse_journal(bigint,date,text,text) TO anon;

COMMIT;
