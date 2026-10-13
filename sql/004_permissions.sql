-- Jalankan sebagai administrator. Nama grup ini khusus proyek UTS.
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='uts_accounting_app') THEN
   CREATE ROLE uts_accounting_app NOLOGIN;
 END IF;
END $$;
REVOKE ALL ON ALL TABLES IN SCHEMA accounting FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA accounting FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA accounting FROM PUBLIC;
GRANT USAGE ON SCHEMA accounting TO uts_accounting_app;
GRANT SELECT ON ALL TABLES IN SCHEMA accounting TO uts_accounting_app;
GRANT EXECUTE ON FUNCTION accounting.submit_cash_voucher(date,text,text,jsonb),
 accounting.reverse_journal(bigint,date,text,text),
 accounting.record_inventory(text,text,int,text,text),
 accounting.verify_journal(bigint) TO uts_accounting_app;
-- Buat login unik lewat psql. Jangan gunakan pemilik skema sebagai pengguna app.
-- CREATE ROLE zidan_uts LOGIN;
-- \password zidan_uts
-- GRANT uts_accounting_app TO zidan_uts;
