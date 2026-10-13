-- Uji integrasi satu sesi pada proyek UTS, tanpa menyimpan transaksi uji.
-- Jalankan sebagai pemilik skema setelah SQL 001-004.
-- Data uji di-rollback lewat subtransaksi; sequence dapat memiliki celah.
-- Ini bukan pengganti tes concurrency dua koneksi dalam tests/test_database.py.
CREATE OR REPLACE FUNCTION pg_temp.uts_cloud_smoke() RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
  checks text[] := ARRAY[]::text[];
  tag text := 'CLOUD-' || md5(clock_timestamp()::text);
  item text := 'T' || substr(md5(clock_timestamp()::text),1,9);
  cash_id bigint; expense_id bigint; hid bigint; rid bigint; draft_id bigint;
  lines jsonb; rejected boolean; audit_before bigint;
  headers_before bigint; stock_before bigint;
BEGIN
  SELECT account_id INTO STRICT cash_id FROM accounting.chart_of_accounts WHERE account_code='1102';
  SELECT account_id INTO STRICT expense_id FROM accounting.chart_of_accounts WHERE account_code='6102';
  SELECT count(*) INTO headers_before FROM accounting.journal_headers;
  SELECT count(*) INTO stock_before FROM accounting.inventory_transactions;
  lines := jsonb_build_array(
    jsonb_build_object('account_id',expense_id,'debit',250000,'credit',0),
    jsonb_build_object('account_id',cash_id,'debit',0,'credit',250000));
  BEGIN
    hid := accounting.submit_cash_voucher(CURRENT_DATE,tag,'Uji cloud listrik',lines);
    IF NOT EXISTS(SELECT 1 FROM accounting.journal_headers WHERE id=hid AND status_posting='POSTED') THEN RAISE EXCEPTION 'Posting gagal'; END IF;
    checks := checks || 'voucher_seimbang_posted'::text;
    IF accounting.verify_journal(hid) IS DISTINCT FROM true THEN RAISE EXCEPTION 'Checksum salah'; END IF;
    checks := checks || 'checksum_sha256_valid'::text;
    IF NOT EXISTS(SELECT 1 FROM accounting.journal_headers WHERE id=hid AND created_by=session_user AND created_at IS NOT NULL) THEN RAISE EXCEPTION 'Metadata salah'; END IF;
    checks := checks || 'aktor_dan_waktu_tercatat'::text;

    rejected := false;
    BEGIN
      PERFORM accounting.submit_cash_voucher(CURRENT_DATE,tag||'-U','Tidak seimbang',jsonb_set(lines,'{1,credit}','249999'));
    EXCEPTION WHEN raise_exception THEN rejected := position('Jurnal tidak seimbang' IN SQLERRM)>0;
    END;
    IF NOT rejected OR EXISTS(SELECT 1 FROM accounting.journal_headers WHERE reference_no=tag||'-U') THEN RAISE EXCEPTION 'Unbalanced tidak atomik'; END IF;
    checks := checks || 'tidak_seimbang_ditolak_atomik'::text;

    rejected := false;
    BEGIN UPDATE accounting.journal_headers SET description='Ubah' WHERE id=hid;
    EXCEPTION WHEN raise_exception THEN rejected := position('POSTED tidak boleh' IN SQLERRM)>0; END;
    IF NOT rejected THEN RAISE EXCEPTION 'Header POSTED dapat diubah'; END IF;
    checks := checks || 'header_posted_terkunci'::text;
    rejected := false;
    BEGIN DELETE FROM accounting.journal_lines WHERE header_id=hid;
    EXCEPTION WHEN raise_exception THEN rejected := position('POSTED dikunci' IN SQLERRM)>0; END;
    IF NOT rejected THEN RAISE EXCEPTION 'Detail POSTED dapat dihapus'; END IF;
    checks := checks || 'detail_posted_terkunci'::text;

    rid := accounting.reverse_journal(hid,CURRENT_DATE,tag||'-R','Uji pembalik');
    IF accounting.verify_journal(rid) IS DISTINCT FROM true OR EXISTS(
      SELECT account_id FROM accounting.journal_lines WHERE header_id IN (hid,rid)
      GROUP BY account_id HAVING sum(debit-credit)<>0) THEN RAISE EXCEPTION 'Reversal gagal'; END IF;
    checks := checks || 'reversal_saling_menghapus_saldo'::text;
    rejected := false;
    BEGIN PERFORM accounting.submit_cash_voucher(CURRENT_DATE,tag,'Duplikat',lines);
    EXCEPTION WHEN unique_violation THEN rejected := true; END;
    IF NOT rejected THEN RAISE EXCEPTION 'Nomor bukti duplikat diterima'; END IF;
    checks := checks || 'nomor_bukti_unik'::text;

    INSERT INTO accounting.inventory_items(item_id,item_name,unit_cost) VALUES(item,'Barang uji sementara',25000);
    PERFORM accounting.record_inventory(item,'PURCHASE',2,tag||'-P','Uji pembelian');
    PERFORM accounting.record_inventory(item,'SALE',1,tag||'-S','Uji penjualan');
    IF (SELECT stock_qty FROM accounting.inventory_items WHERE item_id=item)<>1 OR EXISTS(
      SELECT 1 FROM accounting.inventory_transactions WHERE item_id=item AND accounting.verify_journal(journal_id) IS DISTINCT FROM true)
      THEN RAISE EXCEPTION 'Mutasi stok/jurnal salah'; END IF;
    checks := checks || 'stok_dan_jurnal_terintegrasi'::text;
    SELECT count(*) INTO audit_before FROM accounting.audit_log;
    rejected := false;
    BEGIN PERFORM accounting.record_inventory(item,'SALE',2,tag||'-X','Uji stok kurang');
    EXCEPTION WHEN raise_exception THEN rejected := position('Stok tidak cukup' IN SQLERRM)>0; END;
    IF NOT rejected OR (SELECT stock_qty FROM accounting.inventory_items WHERE item_id=item)<>1
      OR (SELECT count(*) FROM accounting.audit_log)<>audit_before THEN RAISE EXCEPTION 'Oversell tidak atomik'; END IF;
    checks := checks || 'stok_negatif_ditolak_atomik'::text;

    INSERT INTO accounting.journal_headers(transaction_date,reference_no,description)
      VALUES(CURRENT_DATE,tag||'-D','Draft uji') RETURNING id INTO draft_id;
    rejected := false;
    BEGIN INSERT INTO accounting.journal_lines(header_id,account_id,debit,credit) VALUES(draft_id,cash_id,0,0);
    EXCEPTION WHEN check_violation THEN rejected := true; END;
    IF NOT rejected THEN RAISE EXCEPTION 'Baris nol diterima'; END IF;
    checks := checks || 'constraint_baris_nol_ditolak'::text;
    IF has_table_privilege('uts_accounting_app','accounting.journal_headers','UPDATE')
      OR has_function_privilege('uts_accounting_app','accounting.post_journal(bigint)','EXECUTE')
      OR NOT has_function_privilege('uts_accounting_app','accounting.submit_cash_voucher(date,text,text,jsonb)','EXECUTE')
      THEN RAISE EXCEPTION 'Hak akses runtime salah'; END IF;
    checks := checks || 'hak_akses_runtime_terbatas'::text;
    RAISE EXCEPTION USING ERRCODE='Z0001', MESSAGE='Rollback data uji yang berhasil';
  EXCEPTION WHEN SQLSTATE 'Z0001' THEN NULL;
  END;
  IF (SELECT count(*) FROM accounting.journal_headers)<>headers_before
    OR (SELECT count(*) FROM accounting.inventory_transactions)<>stock_before
    OR EXISTS(SELECT 1 FROM accounting.inventory_items WHERE item_id=item) THEN RAISE EXCEPTION 'Data uji tertinggal'; END IF;
  RETURN jsonb_build_object('status','PASS','checks_passed',cardinality(checks),'checks',checks,
    'test_data_rolled_back',true,'server_version',current_setting('server_version'),
    'executed_at',clock_timestamp(),'session_user',session_user,
    'scope','SQL Editor satu sesi; bukan tes koneksi aplikasi atau concurrency cloud');
EXCEPTION WHEN OTHERS THEN
  RETURN jsonb_build_object('status','FAIL','checks_before_failure',checks,'sqlstate',SQLSTATE,'error',SQLERRM);
END $$;
SELECT pg_temp.uts_cloud_smoke() AS hasil_uji_cloud;
