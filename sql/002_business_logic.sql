BEGIN;
SET search_path TO accounting, pg_catalog;

-- Semua fungsi definer mengunci search_path. Hanya API tertentu diberi EXECUTE.
CREATE FUNCTION journal_payload(h journal_headers) RETURNS jsonb
LANGUAGE sql STABLE SET search_path = pg_catalog, accounting AS $$
 SELECT (to_jsonb(h) - 'hash_checksum') || jsonb_build_object(
   'created_at', to_char(h.created_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
   'posted_at', to_char(h.posted_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
   'lines', COALESCE((SELECT jsonb_agg(to_jsonb(l) ORDER BY l.id)
               FROM accounting.journal_lines l WHERE l.header_id = h.id),'[]'::jsonb))
$$;

CREATE FUNCTION guard_header() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, accounting AS $$
DECLARE d numeric; c numeric; n int; cash_d numeric; cash_c numeric;
BEGIN
 IF TG_OP = 'INSERT' THEN
   IF NEW.status_posting <> 'DRAFT' THEN
     RAISE EXCEPTION 'Jurnal baru wajib DRAFT';
   END IF;
   NEW.created_by := session_user;
   NEW.created_at := clock_timestamp();
   NEW.posted_by := NULL; NEW.posted_at := NULL; NEW.hash_checksum := NULL;
   RETURN NEW;
 END IF;
 IF OLD.status_posting = 'POSTED' THEN
   RAISE EXCEPTION 'Jurnal POSTED tidak boleh diubah/dihapus; gunakan reversal';
 END IF;
 IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
 IF NEW.id <> OLD.id OR NEW.created_by <> OLD.created_by
    OR NEW.created_at <> OLD.created_at THEN
   RAISE EXCEPTION 'Identitas dan metadata penciptaan tidak boleh diubah';
 END IF;
 IF NEW.status_posting = 'POSTED' THEN
   SELECT count(*), COALESCE(sum(debit),0), COALESCE(sum(credit),0)
     INTO n,d,c FROM accounting.journal_lines WHERE header_id = NEW.id;
   IF n < 2 OR d <= 0 OR d <> c THEN
     RAISE EXCEPTION 'Jurnal tidak seimbang: debit %, kredit %, baris %',d,c,n;
   END IF;
   IF NEW.voucher_type = 'CASH_OUT' THEN
     IF EXISTS (SELECT 1 FROM accounting.journal_lines l
       JOIN accounting.chart_of_accounts a USING(account_id)
       WHERE l.header_id=NEW.id AND a.account_code='1103') THEN
       RAISE EXCEPTION 'Gunakan modul persediaan untuk perubahan akun persediaan';
     END IF;
     SELECT COALESCE(sum(l.debit),0), COALESCE(sum(l.credit),0)
       INTO cash_d,cash_c FROM accounting.journal_lines l
       JOIN accounting.chart_of_accounts a USING(account_id)
       WHERE l.header_id = NEW.id AND a.is_cash;
     IF cash_d <> 0 OR cash_c <= 0 THEN
       RAISE EXCEPTION 'Voucher kas keluar wajib mengkredit kas/bank tanpa debit kas';
     END IF;
   END IF;
   NEW.posted_by := session_user; NEW.posted_at := clock_timestamp();
   NEW.hash_checksum := encode(sha256(convert_to(
       accounting.journal_payload(NEW)::text,'UTF8')),'hex');
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER guard_header BEFORE INSERT OR UPDATE OR DELETE ON journal_headers
FOR EACH ROW EXECUTE FUNCTION guard_header();

CREATE FUNCTION guard_line() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, accounting AS $$
DECLARE hid bigint; posting text;
BEGIN
 IF TG_OP = 'UPDATE' AND (NEW.header_id <> OLD.header_id OR NEW.id <> OLD.id) THEN
   RAISE EXCEPTION 'Identitas baris dan header tidak boleh dipindahkan';
 END IF;
 IF TG_OP = 'DELETE' THEN hid := OLD.header_id; ELSE hid := NEW.header_id; END IF;
 -- Lock header yang sama dengan operasi posting, sebelum mengubah detail.
 SELECT status_posting INTO posting FROM accounting.journal_headers
   WHERE id = hid FOR UPDATE;
 IF posting = 'POSTED' THEN RAISE EXCEPTION 'Detail jurnal POSTED dikunci'; END IF;
 IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER guard_line BEFORE INSERT OR UPDATE OR DELETE ON journal_lines
FOR EACH ROW EXECUTE FUNCTION guard_line();

CREATE FUNCTION capture_audit() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, accounting AS $$
DECLARE o jsonb; n jsonb; k text;
BEGIN
 IF TG_OP <> 'INSERT' THEN o := to_jsonb(OLD); END IF;
 IF TG_OP <> 'DELETE' THEN n := to_jsonb(NEW); END IF;
 k := COALESCE(n->>'id',o->>'id',n->>'trx_id',o->>'trx_id',n->>'item_id',o->>'item_id');
 INSERT INTO accounting.audit_log(table_name,operation,row_key,old_data,new_data)
 VALUES (TG_TABLE_NAME,TG_OP,k,o,n);
 RETURN NULL;
END $$;
CREATE TRIGGER audit_header AFTER INSERT OR UPDATE OR DELETE ON journal_headers
FOR EACH ROW EXECUTE FUNCTION capture_audit();
CREATE TRIGGER audit_line AFTER INSERT OR UPDATE OR DELETE ON journal_lines
FOR EACH ROW EXECUTE FUNCTION capture_audit();
CREATE TRIGGER audit_item AFTER INSERT OR UPDATE OR DELETE ON inventory_items
FOR EACH ROW EXECUTE FUNCTION capture_audit();
CREATE TRIGGER audit_inventory AFTER INSERT OR UPDATE OR DELETE ON inventory_transactions
FOR EACH ROW EXECUTE FUNCTION capture_audit();

CREATE FUNCTION deny_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Tabel % bersifat append-only; koreksi dengan transaksi baru',TG_TABLE_NAME; END $$;
CREATE TRIGGER immutable_audit BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION deny_change();
CREATE TRIGGER immutable_inventory BEFORE UPDATE OR DELETE ON inventory_transactions
FOR EACH ROW EXECUTE FUNCTION deny_change();
CREATE TRIGGER no_truncate_audit BEFORE TRUNCATE ON audit_log
FOR EACH STATEMENT EXECUTE FUNCTION deny_change();
CREATE TRIGGER no_truncate_headers BEFORE TRUNCATE ON journal_headers
FOR EACH STATEMENT EXECUTE FUNCTION deny_change();
CREATE TRIGGER no_truncate_lines BEFORE TRUNCATE ON journal_lines
FOR EACH STATEMENT EXECUTE FUNCTION deny_change();
CREATE TRIGGER no_truncate_inventory BEFORE TRUNCATE ON inventory_transactions
FOR EACH STATEMENT EXECUTE FUNCTION deny_change();

CREATE FUNCTION post_journal(p_id bigint) RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, accounting AS $$
DECLARE s text;
BEGIN
 PERFORM 1 FROM accounting.journal_headers WHERE id=p_id FOR UPDATE;
 SELECT status_posting INTO s FROM accounting.journal_headers WHERE id=p_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'Jurnal tidak ditemukan'; END IF;
 IF s <> 'DRAFT' THEN RAISE EXCEPTION 'Jurnal sudah POSTED'; END IF;
 UPDATE accounting.journal_headers SET status_posting='POSTED' WHERE id=p_id;
 RETURN p_id;
END $$;

-- API tunggal untuk voucher web: simpan semua baris dan posting secara atomik.
CREATE FUNCTION submit_cash_voucher(p_date date, p_ref text, p_desc text, p_lines jsonb)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, accounting AS $$
DECLARE hid bigint; entry jsonb; d numeric; c numeric;
BEGIN
 IF jsonb_typeof(p_lines) IS DISTINCT FROM 'array'
    OR jsonb_array_length(p_lines) NOT BETWEEN 2 AND 100 THEN
   RAISE EXCEPTION 'Voucher membutuhkan 2 sampai 100 baris';
 END IF;
 INSERT INTO accounting.journal_headers(transaction_date,reference_no,description,voucher_type)
 VALUES(p_date,p_ref,p_desc,'CASH_OUT') RETURNING id INTO hid;
 FOR entry IN SELECT * FROM jsonb_array_elements(p_lines) LOOP
   d := (entry->>'debit')::numeric; c := (entry->>'credit')::numeric;
   IF d IS NULL OR c IS NULL OR d <> round(d,2) OR c <> round(c,2) THEN
     RAISE EXCEPTION 'Nominal wajib terisi dan maksimal dua angka desimal';
   END IF;
   INSERT INTO accounting.journal_lines(header_id,account_id,debit,credit)
   VALUES(hid,(entry->>'account_id')::bigint,d,c);
 END LOOP;
 PERFORM accounting.post_journal(hid);
 RETURN hid;
END $$;

CREATE FUNCTION reverse_journal(p_id bigint,p_date date,p_ref text,p_reason text)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, accounting AS $$
DECLARE original accounting.journal_headers; hid bigint;
BEGIN
 SELECT * INTO original FROM accounting.journal_headers WHERE id=p_id FOR UPDATE;
 IF NOT FOUND OR original.status_posting <> 'POSTED' THEN
   RAISE EXCEPTION 'Hanya jurnal POSTED yang boleh dibalik';
 END IF;
 IF original.voucher_type IN ('INVENTORY','REVERSAL') THEN
   RAISE EXCEPTION 'Jurnal stok dikoreksi lewat ADJUSTMENT; reversal tidak dibalik ulang';
 END IF;
 IF p_date < original.transaction_date OR p_date IS NULL
      OR p_reason IS NULL OR btrim(p_reason) = '' THEN
   RAISE EXCEPTION 'Tanggal reversal tidak boleh lebih awal dan alasan wajib diisi';
 END IF;
 INSERT INTO accounting.journal_headers(transaction_date,reference_no,description,voucher_type,reversal_of)
 VALUES(p_date,p_ref,'Pembalik '||original.reference_no||': '||p_reason,'REVERSAL',p_id)
 RETURNING id INTO hid;
 INSERT INTO accounting.journal_lines(header_id,account_id,debit,credit)
 SELECT hid,account_id,credit,debit FROM accounting.journal_lines WHERE header_id=p_id ORDER BY id;
 PERFORM accounting.post_journal(hid);
 RETURN hid;
END $$;

CREATE FUNCTION verify_journal(p_id bigint) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, accounting AS $$
 SELECT h.status_posting = 'POSTED' AND h.hash_checksum =
   encode(sha256(convert_to(accounting.journal_payload(h)::text,'UTF8')),'hex')
 FROM accounting.journal_headers h WHERE h.id=p_id
$$;

CREATE FUNCTION trg_update_stock_and_journal() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, accounting AS $$
DECLARE current_qty int; cost numeric; delta bigint; amount numeric;
        hid bigint; debit_code text; credit_code text;
BEGIN
 -- BEFORE INSERT: lock diambil sebelum FK INSERT memperoleh KEY SHARE.
 SELECT stock_qty,unit_cost INTO current_qty,cost
 FROM accounting.inventory_items WHERE item_id=NEW.item_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Barang tidak ditemukan'; END IF;
 IF NEW.qty IS NULL OR NEW.trx_type IS NULL
    OR NEW.trx_type NOT IN ('PURCHASE','SALE','ADJUSTMENT')
    OR (NEW.trx_type IN ('PURCHASE','SALE') AND NEW.qty <= 0)
    OR (NEW.trx_type='ADJUSTMENT' AND NEW.qty=0) THEN
   RAISE EXCEPTION 'Jenis atau kuantitas transaksi tidak valid';
 END IF;
 delta := CASE WHEN NEW.trx_type='SALE' THEN -NEW.qty::bigint ELSE NEW.qty::bigint END;
 IF current_qty::bigint + delta < 0 THEN
   RAISE EXCEPTION 'Stok tidak cukup: tersedia %, perubahan %',current_qty,delta;
 END IF;
 UPDATE accounting.inventory_items SET stock_qty=stock_qty+delta WHERE item_id=NEW.item_id;
 NEW.unit_cost_snapshot := cost;
 NEW.created_by := session_user; NEW.trx_date := clock_timestamp();
 amount := abs(delta)*cost;
 IF NEW.trx_type='PURCHASE' THEN debit_code:='1103'; credit_code:='2101';
 ELSIF NEW.trx_type='SALE' THEN debit_code:='5101'; credit_code:='1103';
 ELSIF delta>0 THEN debit_code:='1103'; credit_code:='5102';
 ELSE debit_code:='5102'; credit_code:='1103'; END IF;
 INSERT INTO accounting.journal_headers(transaction_date,reference_no,description,voucher_type)
 VALUES((NEW.trx_date AT TIME ZONE 'Asia/Jakarta')::date,'INV-'||NEW.reference_no,
        NEW.trx_type||' '||NEW.item_id||': '||NEW.reason,'INVENTORY') RETURNING id INTO hid;
 INSERT INTO accounting.journal_lines(header_id,account_id,debit,credit)
 SELECT hid,account_id,CASE WHEN account_code=debit_code THEN amount ELSE 0 END,
        CASE WHEN account_code=credit_code THEN amount ELSE 0 END
 FROM accounting.chart_of_accounts WHERE account_code IN (debit_code,credit_code);
 PERFORM accounting.post_journal(hid);
 NEW.journal_id:=hid;
 RETURN NEW;
END $$;
CREATE TRIGGER update_stock_and_journal BEFORE INSERT ON inventory_transactions
FOR EACH ROW EXECUTE FUNCTION trg_update_stock_and_journal();

CREATE FUNCTION record_inventory(p_item text,p_type text,p_qty int,p_ref text,p_reason text)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, accounting AS $$
DECLARE tid bigint;
BEGIN
 -- Sisakan ruang prefix INV- pada journal_headers.reference_no.
 IF length(p_ref)>76 THEN RAISE EXCEPTION 'Referensi stok maksimal 76 karakter'; END IF;
 INSERT INTO accounting.inventory_transactions(item_id,trx_type,qty,reference_no,reason)
 VALUES(p_item,p_type,p_qty,p_ref,p_reason) RETURNING trx_id INTO tid;
 RETURN tid;
END $$;

CREATE VIEW ledger_balances AS
 SELECT a.account_code,a.account_name,a.normal_balance,a.report_class,
 COALESCE(sum(l.debit) FILTER(WHERE h.status_posting='POSTED'),0) AS total_debit,
 COALESCE(sum(l.credit) FILTER(WHERE h.status_posting='POSTED'),0) AS total_credit
 FROM chart_of_accounts a LEFT JOIN journal_lines l USING(account_id)
 LEFT JOIN journal_headers h ON h.id=l.header_id
 GROUP BY a.account_id;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA accounting FROM PUBLIC;
COMMIT;
