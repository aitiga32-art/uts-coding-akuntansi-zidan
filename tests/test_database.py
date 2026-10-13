import os
import time
import uuid
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import psycopg
from psycopg.types.json import Jsonb

APP=os.environ.get("TEST_DATABASE_URL")
ADMIN=os.environ.get("TEST_ADMIN_DATABASE_URL")


@unittest.skipUnless(APP and ADMIN,"Perlu TEST_DATABASE_URL dan TEST_ADMIN_DATABASE_URL pada DB uji khusus")
class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tag=uuid.uuid4().hex[:10]
        with psycopg.connect(ADMIN) as c:
            self.ids=dict(c.execute("SELECT account_code,account_id FROM accounting.chart_of_accounts").fetchall())

    def query(self,sql,params=(),admin=False):
        with psycopg.connect(ADMIN if admin else APP) as c:
            cursor=c.execute(sql,params)
            return cursor.fetchall() if cursor.description else []

    def voucher(self,delta=0,ref=None):
        lines=[{"account_id":self.ids["6101"],"debit":"250000.00","credit":"0"},
               {"account_id":self.ids["1102"],"debit":"0","credit":str(250000+delta)}]
        return self.query("SELECT accounting.submit_cash_voucher(%s,%s,%s,%s)",
            (date(2026,10,13),ref or self.tag,"Uji voucher",Jsonb(lines)))[0][0]

    def new_item(self,qty=2):
        item=self.tag[:10]
        self.query("INSERT INTO accounting.inventory_items(item_id,item_name,unit_cost) VALUES(%s,'Barang uji',10000)",(item,),True)
        if qty: self.query("SELECT accounting.record_inventory(%s,'PURCHASE',%s,%s,'Saldo uji')",(item,qty,'P'+self.tag))
        return item

    def draft(self):
        return self.query("INSERT INTO accounting.journal_headers(transaction_date,reference_no,description) VALUES(CURRENT_DATE,%s,'Uji') RETURNING id",(self.tag,),True)[0][0]

    def test_balanced_post_hash_and_actor(self):
        hid=self.voucher()
        row=self.query("SELECT status_posting,created_by,hash_checksum,accounting.verify_journal(id) FROM accounting.journal_headers WHERE id=%s",(hid,))[0]
        self.assertEqual(row[0],"POSTED"); self.assertEqual(len(row[2]),64); self.assertTrue(row[3])
        actor=self.query("SELECT session_user")[0][0]
        self.assertEqual(row[1],actor)
        self.assertEqual(self.query("SELECT actor FROM accounting.audit_log WHERE table_name='journal_headers' AND row_key=%s ORDER BY audit_id LIMIT 1",(str(hid),))[0][0],actor)

    def test_unbalanced_direct_rpc_rollback(self):
        with self.assertRaises(psycopg.Error): self.voucher(delta=1)
        self.assertEqual(self.query("SELECT count(*) FROM accounting.journal_headers WHERE reference_no=%s",(self.tag,))[0][0],0)

    def test_line_constraints(self):
        hid=self.draft()
        for d,c in [(-1,0),(0,0),(2,2),(None,1),('NaN',0)]:
            with self.subTest(d=d,c=c),self.assertRaises(psycopg.Error):
                self.query("INSERT INTO accounting.journal_lines(header_id,account_id,debit,credit) VALUES(%s,%s,%s,%s)",(hid,self.ids["1101"],d,c),True)

    def test_foreign_key_rejects_unknown_account(self):
        hid=self.draft()
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self.query("INSERT INTO accounting.journal_lines(header_id,account_id,debit) VALUES(%s,999999999,1)",(hid,),True)

    def test_on_delete_restrict(self):
        hid=self.draft()
        self.query("INSERT INTO accounting.journal_lines(header_id,account_id,debit) VALUES(%s,%s,1)",(hid,self.ids["1101"]),True)
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self.query("DELETE FROM accounting.journal_headers WHERE id=%s",(hid,),True)

    def test_empty_post_rejected(self):
        hid=self.draft()
        with self.assertRaises(psycopg.Error): self.query("SELECT accounting.post_journal(%s)",(hid,),True)

    def test_posted_header_immutable(self):
        hid=self.voucher()
        for sql in ["UPDATE accounting.journal_headers SET description='Rusak' WHERE id=%s", "DELETE FROM accounting.journal_headers WHERE id=%s", "UPDATE accounting.journal_headers SET status_posting='DRAFT' WHERE id=%s"]:
            with self.subTest(sql=sql),self.assertRaises(psycopg.Error): self.query(sql,(hid,),True)

    def test_posted_lines_immutable(self):
        hid=self.voucher()
        for sql in ["UPDATE accounting.journal_lines SET debit=999 WHERE header_id=%s", "DELETE FROM accounting.journal_lines WHERE header_id=%s"]:
            with self.subTest(sql=sql),self.assertRaises(psycopg.Error): self.query(sql,(hid,),True)
        with self.assertRaises(psycopg.Error):
            self.query("INSERT INTO accounting.journal_lines(header_id,account_id,debit) VALUES(%s,%s,1)",(hid,self.ids["1101"]),True)

    def test_reversal_offsets_original(self):
        hid=self.voucher()
        rid=self.query("SELECT accounting.reverse_journal(%s,%s,%s,'Salah pencatatan')",(hid,date(2026,10,13),'R'+self.tag))[0][0]
        balances=self.query("SELECT account_id,sum(debit-credit) FROM accounting.journal_lines WHERE header_id IN (%s,%s) GROUP BY account_id",(hid,rid))
        self.assertTrue(all(v==0 for _,v in balances))
        self.assertTrue(self.query("SELECT accounting.verify_journal(%s)",(rid,))[0][0])
        with self.assertRaises(psycopg.Error):
            self.query("SELECT accounting.reverse_journal(%s,%s,%s,'Kedua')",(hid,date(2026,10,13),'R2'+self.tag))

    def test_checksum_timezone_independent(self):
        hid=self.voucher()
        with psycopg.connect(APP) as c:
            for tz in ['UTC','Asia/Jakarta','America/New_York']:
                c.execute("SELECT set_config('TimeZone',%s,true)",(tz,))
                self.assertTrue(c.execute("SELECT accounting.verify_journal(%s)",(hid,)).fetchone()[0])

    def test_duplicate_reference_rejected(self):
        self.voucher()
        with self.assertRaises(psycopg.errors.UniqueViolation): self.voucher()

    def test_cash_out_requires_cash_credit(self):
        entries=[{"account_id":self.ids['6101'],"debit":10,"credit":0},{"account_id":self.ids['2101'],"debit":0,"credit":10}]
        with self.assertRaises(psycopg.Error): self.query("SELECT accounting.submit_cash_voucher(CURRENT_DATE,%s,'Nonkas',%s)",(self.tag,Jsonb(entries)))

    def test_cash_voucher_cannot_bypass_stock_module(self):
        entries=[{"account_id":self.ids['1103'],"debit":10,"credit":0},{"account_id":self.ids['1102'],"debit":0,"credit":10}]
        with self.assertRaises(psycopg.Error):
            self.query("SELECT accounting.submit_cash_voucher(CURRENT_DATE,%s,'Stok manual',%s)",(self.tag,Jsonb(entries)))

    def test_checksum_detects_privileged_tamper(self):
        hid=self.voucher()
        # Hanya simulasi serangan owner di DB uji; DDL/data selalu di-rollback.
        with psycopg.connect(ADMIN) as c:
            try:
                c.execute("ALTER TABLE accounting.journal_headers DISABLE TRIGGER guard_header")
                c.execute("UPDATE accounting.journal_headers SET description='Tampered' WHERE id=%s",(hid,))
                self.assertFalse(c.execute("SELECT accounting.verify_journal(%s)",(hid,)).fetchone()[0])
            finally: c.rollback()
        self.assertTrue(self.query("SELECT accounting.verify_journal(%s)",(hid,))[0][0])

    def test_inventory_purchase_sale_and_journal(self):
        item=self.new_item(2)
        tid=self.query("SELECT accounting.record_inventory(%s,'SALE',1,%s,'Terjual')",(item,'S'+self.tag))[0][0]
        self.assertEqual(self.query("SELECT stock_qty FROM accounting.inventory_items WHERE item_id=%s",(item,))[0][0],1)
        self.assertEqual(self.query("SELECT unit_cost_snapshot FROM accounting.inventory_transactions WHERE trx_id=%s",(tid,))[0][0],10000)
        self.assertTrue(self.query("SELECT accounting.verify_journal(journal_id) FROM accounting.inventory_transactions WHERE trx_id=%s",(tid,))[0][0])

    def test_negative_stock_atomic_rollback(self):
        item=self.new_item(1)
        count_before=self.query("SELECT count(*) FROM accounting.audit_log")[0][0]
        with self.assertRaises(psycopg.Error): self.query("SELECT accounting.record_inventory(%s,'SALE',2,%s,'Terlalu banyak')",(item,'S'+self.tag))
        self.assertEqual(self.query("SELECT stock_qty FROM accounting.inventory_items WHERE item_id=%s",(item,))[0][0],1)
        self.assertEqual(self.query("SELECT count(*) FROM accounting.audit_log")[0][0],count_before)

    def test_adjustments_signed_and_guarded(self):
        item=self.new_item(1)
        self.query("SELECT accounting.record_inventory(%s,'ADJUSTMENT',2,%s,'Tambah')",(item,'A'+self.tag))
        self.query("SELECT accounting.record_inventory(%s,'ADJUSTMENT',-1,%s,'Kurang')",(item,'B'+self.tag))
        self.assertEqual(self.query("SELECT stock_qty FROM accounting.inventory_items WHERE item_id=%s",(item,))[0][0],2)
        with self.assertRaises(psycopg.Error): self.query("SELECT accounting.record_inventory(%s,'ADJUSTMENT',-3,%s,'Minus')",(item,'C'+self.tag))

    def test_qty_zero_negative_or_bad_type(self):
        item=self.new_item(1)
        for kind,qty in [('SALE',0),('PURCHASE',-1),('ADJUSTMENT',0),('BAD',1)]:
            with self.subTest(kind=kind,qty=qty),self.assertRaises(psycopg.Error):
                self.query("SELECT accounting.record_inventory(%s,%s,%s,%s,'Uji')",(item,kind,qty,'X'+self.tag))

    def test_runtime_cannot_bypass_api(self):
        for sql in ["UPDATE accounting.inventory_items SET stock_qty=999", "DELETE FROM accounting.audit_log", "SELECT accounting.post_journal(1)", "TRUNCATE accounting.journal_lines"]:
            with self.subTest(sql=sql),self.assertRaises(psycopg.errors.InsufficientPrivilege): self.query(sql)

    def test_audit_and_stock_events_append_only(self):
        item=self.new_item(1)
        with self.assertRaises(psycopg.Error): self.query("UPDATE accounting.inventory_transactions SET qty=9 WHERE item_id=%s",(item,),True)
        with self.assertRaises(psycopg.Error): self.query("DELETE FROM accounting.audit_log WHERE audit_id=(SELECT min(audit_id) FROM accounting.audit_log)",(),True)

    def test_two_cashiers_last_unit(self):
        item=self.new_item(1)
        a=psycopg.connect(APP)
        b=psycopg.connect(APP)
        bpid=b.info.backend_pid
        try:
            a.execute("SELECT accounting.record_inventory(%s,'SALE',1,%s,'Kasir A')",(item,'A'+self.tag))
            def cashier_b():
                try:
                    b.execute("SET LOCAL statement_timeout='8s'")
                    b.execute("SELECT accounting.record_inventory(%s,'SALE',1,%s,'Kasir B')",(item,'B'+self.tag))
                    b.commit(); return 'COMMITTED'
                except psycopg.Error as exc:
                    b.rollback(); return exc.diag.message_primary
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(cashier_b)
                locked=False
                deadline=time.monotonic()+4
                while time.monotonic()<deadline:
                    wait=self.query("SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s",(bpid,),True)
                    if wait and wait[0][0]=='Lock': locked=True; break
                    time.sleep(.05)
                a.commit()
                outcome=future.result(timeout=10)
                self.assertTrue(locked,"Kasir B harus benar-benar menunggu row lock")
                self.assertIn('Stok tidak cukup',outcome)
            self.assertEqual(self.query("SELECT stock_qty FROM accounting.inventory_items WHERE item_id=%s",(item,))[0][0],0)
            self.assertEqual(self.query("SELECT count(*) FROM accounting.inventory_transactions WHERE item_id=%s AND trx_type='SALE'",(item,))[0][0],1)
        finally:
            a.close();b.close()
