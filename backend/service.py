from datetime import date

import httpx
import psycopg
from psycopg.types.json import Jsonb

from backend.db import connection
from backend import supabase_rest
from backend.validation import validate_lines


def read(sql, params=()):
    with connection() as conn:
        return conn.execute(sql, params).fetchall()


def accounts():
    if supabase_rest.configured():
        return supabase_rest.rpc("uts_accounts")
    return read("SELECT * FROM accounting.chart_of_accounts ORDER BY account_code")


def items():
    if supabase_rest.configured():
        return supabase_rest.rpc("uts_items")
    return read("SELECT *, stock_qty*unit_cost AS stock_value FROM accounting.inventory_items ORDER BY item_id")


def journals():
    if supabase_rest.configured():
        rows = supabase_rest.rpc("uts_journals")
        for row in rows:
            row["transaction_date"] = date.fromisoformat(row["transaction_date"])
        return rows
    return read("""SELECT h.id,h.transaction_date,h.reference_no,h.description,h.voucher_type,
        h.status_posting,h.reversal_of,h.created_by,h.created_at,h.hash_checksum,
        (SELECT sum(debit) FROM accounting.journal_lines WHERE header_id=h.id) AS amount,
        accounting.verify_journal(h.id) AS checksum_valid
        FROM accounting.journal_headers h WHERE h.status_posting='POSTED'
        ORDER BY h.id DESC LIMIT 200""")


def journal_lines(header_id):
    if supabase_rest.configured():
        return supabase_rest.rpc("uts_journal_lines", {"p_header_id": header_id})
    return read("""SELECT a.account_code,a.account_name,l.debit,l.credit
        FROM accounting.journal_lines l JOIN accounting.chart_of_accounts a USING(account_id)
        WHERE l.header_id=%s ORDER BY l.id""", (header_id,))


def audit():
    if supabase_rest.configured():
        return supabase_rest.rpc("uts_audit")
    return read("SELECT * FROM accounting.audit_log ORDER BY audit_id DESC LIMIT 200")


def submit_voucher(trx_date, ref, description, lines):
    clean, _, _ = validate_lines(lines)
    if not ref.strip() or not description.strip():
        raise ValueError("Nomor bukti dan deskripsi wajib diisi.")
    if supabase_rest.configured():
        return supabase_rest.rpc("uts_submit_cash_voucher", {
            "p_date": trx_date.isoformat(), "p_ref": ref.strip(),
            "p_desc": description.strip(), "p_lines": clean,
        })
    with connection() as conn:
        return conn.execute("SELECT accounting.submit_cash_voucher(%s,%s,%s,%s) AS id",
            (trx_date, ref.strip(), description.strip(), Jsonb(clean))).fetchone()["id"]


def inventory(item, kind, qty, ref, reason):
    if not ref.strip() or not reason.strip():
        raise ValueError("Nomor referensi dan alasan wajib diisi.")
    if supabase_rest.configured():
        return supabase_rest.rpc("uts_record_inventory", {
            "p_item": item, "p_type": kind, "p_qty": qty,
            "p_ref": ref.strip(), "p_reason": reason.strip(),
        })
    with connection() as conn:
        return conn.execute("SELECT accounting.record_inventory(%s,%s,%s,%s,%s) AS id",
            (item, kind, qty, ref.strip(), reason.strip())).fetchone()["id"]


def reverse(header_id, trx_date, ref, reason):
    if supabase_rest.configured():
        return supabase_rest.rpc("uts_reverse_journal", {
            "p_id": header_id, "p_date": trx_date.isoformat(),
            "p_ref": ref.strip(), "p_reason": reason.strip(),
        })
    with connection() as conn:
        return conn.execute("SELECT accounting.reverse_journal(%s,%s,%s,%s) AS id",
            (header_id, trx_date, ref.strip(), reason.strip())).fetchone()["id"]


def error_message(exc):
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            return exc.response.json().get("message", "Permintaan ditolak oleh Supabase.")
        except Exception:
            return "Supabase tidak dapat dihubungi. Periksa konfigurasi proyek."
    if isinstance(exc, httpx.RequestError):
        return "Supabase tidak dapat dihubungi. Periksa koneksi internet."
    if isinstance(exc, psycopg.errors.UniqueViolation):
        return "Nomor bukti sudah dipakai atau jurnal sudah memiliki pembalik. Periksa daftar jurnal."
    if isinstance(exc, psycopg.errors.InsufficientPrivilege):
        return "Hak akses database belum sesuai. Periksa sql/004_permissions.sql."
    if isinstance(exc, psycopg.OperationalError):
        return "Database tidak dapat dihubungi. Periksa koneksi dan konfigurasi server."
    if isinstance(exc, psycopg.Error):
        return exc.diag.message_primary or "Transaksi ditolak oleh database."
    if isinstance(exc, (ValueError, RuntimeError)):
        return str(exc)
    return "Operasi belum berhasil. Periksa log server."
