from datetime import date
from decimal import Decimal
import uuid

import pandas as pd
import streamlit as st

from backend import service
from backend.validation import money, validate_lines

# Konfigurasi halaman dan CSS untuk responsivitas di layar sempit
st.set_page_config(page_title="Voucher | Zidan", page_icon="📒", layout="wide")
st.markdown("""<style>
.block-container{padding-top:2rem;max-width:1280px}
h1{letter-spacing:-.035em} 
[data-testid="stMetric"]{background:white;border:1px solid #e0e7ee;border-radius:12px;padding:16px} 
[data-testid="stSidebar"]{border-right:1px solid #e0e7ee}
@media(max-width:800px){[data-testid="stMetricValue"]{font-size:1.2rem!important}}
</style>""", unsafe_allow_html=True)

# Komponen Sidebar
with st.sidebar:
    st.markdown("## VOUCHER")
    st.caption("AKUNTANSI · UTS 2026")
    st.divider()
    st.write("Zidan Anargya Elian Mulyono")
    st.caption("NIM 12030124130141")
    st.divider()
    st.caption("Kas keluar, persediaan, dan jejak audit dalam satu ruang kerja.")
    st.info("Transaksi yang sudah diposting dikoreksi melalui jurnal pembalik.")

st.title("Ruang kerja akuntansi")
st.caption("Catat transaksi dengan jurnal seimbang dan jejak audit yang bisa diperiksa.")

# Notifikasi sesi (flash messages)
if "notice" in st.session_state:
    st.success(st.session_state.pop("notice"))

# Uji koneksi database secara reaktif, sembunyikan kredensial
try:
    coa = service.accounts()
    all_items = service.items()
    all_journals = service.journals()
except Exception as exc:
    st.error(service.error_message(exc))
    st.info("Koneksi database terputus. Pastikan variabel lingkungan DATABASE_URL terkonfigurasi dengan benar.")
    st.code('$env:DATABASE_URL="postgresql://USER:PASSWORD@HOST:5432/DATABASE"\npython -m streamlit run app.py', language="powershell")
    st.stop()

def rupiah(value):
    """Format angka menjadi Rupiah Indonesia."""
    return "Rp " + f"{Decimal(str(value)):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")

# Ringkasan Eksekutif (Metrics)
m1, m2, m3 = st.columns(3)
m1.metric("Voucher tercatat", len(all_journals))
m2.metric("Nilai persediaan", rupiah(sum(x["stock_value"] for x in all_items)))
m3.metric("Integritas jurnal", "Valid" if all(x.get("checksum_valid", False) for x in all_journals) else "Perlu diperiksa")
st.caption("Ringkasan jurnal menampilkan maksimal 200 transaksi terbaru.")

voucher_tab, stock_tab, journal_tab, audit_tab = st.tabs(["Kas keluar", "Persediaan", "Jurnal & pembalik", "Jejak audit"])

with voucher_tab:
    st.subheader("Voucher kas keluar")
    st.write("Lengkapi bukti transaksi, lalu isi pasangan akun debit dan kredit.")
    
    # Kunci unik untuk mereset UI (reference/deskripsi) setelah submit berhasil
    if "voucher_key" not in st.session_state:
        st.session_state.voucher_key = uuid.uuid4().hex[:8].upper()
    
    a, b = st.columns([1, 2])
    trx_date = a.date_input("Tanggal transaksi", date.today())
    reference = b.text_input("Nomor bukti", "KK-" + st.session_state.voucher_key, max_chars=80, key="ref_"+st.session_state.voucher_key)
    description = st.text_input("Deskripsi", "Pembayaran perlengkapan kantor", key="desc_"+st.session_state.voucher_key)
    
    # Pemetaan COA ke dalam format yang ramah UI
    labels = {f'{x["account_code"]} · {x["account_name"]}': x for x in coa}
    codes = {x["account_code"]: label for label, x in labels.items()}
    
    # Data bawaan untuk formulir (Kas Keluar)
    initial = pd.DataFrame([
        {"Akun": codes.get("6101"), "Debit": 250000.0, "Kredit": 0.0},
        {"Akun": codes.get("1102"), "Debit": 0.0, "Kredit": 250000.0}
    ])
    
    # Tabel dinamis
    edited = st.data_editor(
        initial, 
        num_rows="dynamic", 
        hide_index=True, 
        width="stretch",
        key="journal_editor_" + st.session_state.voucher_key, 
        column_config={
            "Akun": st.column_config.SelectboxColumn(options=list(labels), required=True, width="large"),
            "Debit": st.column_config.NumberColumn(min_value=0.0, step=0.01, format="%.2f", default=0.0, required=True),
            "Kredit": st.column_config.NumberColumn(min_value=0.0, step=0.01, format="%.2f", default=0.0, required=True)
        }
    )
    
    entries = []
    total_d = Decimal("0.00")
    total_c = Decimal("0.00")
    issue = ""
    edited_records = edited.to_dict("records")
    
    # Proses pengecekan & perhitungan antarmuka
    try:
        # Cek kelengkapan baris dan hitung total sebelum dikirim ke validator strict
        for i, row in enumerate(edited_records):
            akun_label = row.get("Akun")
            chosen = labels.get(akun_label) if pd.notna(akun_label) else None
            
            if chosen is None:
                raise ValueError("Terdapat baris yang belum memilih akun. Hapus baris kosong atau pilih akun.")
            
            # Biarkan money() yang menangani tipe data kosong/NaN dengan strict
            d, c = money(row.get("Debit")), money(row.get("Kredit"))
            total_d += d
            total_c += c
            
            entries.append({"account_id": chosen["account_id"], "debit": str(d), "credit": str(c)})
        
        # Validasi dasar seperti text description
        if not reference.strip() or not description.strip():
            raise ValueError("Nomor bukti dan deskripsi wajib diisi.")
            
        # Panggil validator strict dari backend untuk menyelaraskan aturan database
        validate_lines(entries)
        
        # Pengecekan aturan spesifik: Voucher Kas Keluar
        selected_accounts = [labels.get(row.get("Akun")) if pd.notna(row.get("Akun")) else None for row in edited_records]
        
        # Menghitung agregat kas
        cash_d = sum(money(r.get("Debit")) for r, a in zip(edited_records, selected_accounts) if a and a["is_cash"])
        cash_c = sum(money(r.get("Kredit")) for r, a in zip(edited_records, selected_accounts) if a and a["is_cash"])
        
        if cash_d != 0 or cash_c <= 0:
            raise ValueError("Voucher kas keluar harus mengkredit kas/bank tanpa mendebit kas.")
            
        if any(acc and acc["account_code"] == "1103" for acc in selected_accounts):
            raise ValueError("Perubahan akun persediaan dagang harus melalui tab Persediaan (Mutasi Stok).")

    except ValueError as exc:
        issue = str(exc)

    # Menampilkan Totals dan Selisih (Selalu ditampilkan meskipun ada issue)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total debit", rupiah(total_d))
    c2.metric("Total kredit", rupiah(total_c))
    
    # Warna peringatan jika selisih tidak nol
    diff = total_d - total_c
    c3.metric("Selisih", rupiah(diff), delta=None if diff == 0 else "Tidak Seimbang", delta_color="inverse")

    if issue:
        st.warning(issue)
    else:
        st.success("✅ Jurnal seimbang dan memenuhi syarat. Voucher siap diposting.")
        
    st.caption("Tambahkan baris baru melalui tabel. Klik di luar sel tabel setelah mengetik untuk memperbarui nominal.")
    
    # Tombol submit dimatikan (disabled) jika terdapat isu
    if st.button("Submit & posting", type="primary", disabled=bool(issue), key="submit_voucher"):
        try:
            # Memanggil API backend secara atomik
            hid = service.submit_voucher(trx_date, reference, description, entries)
            st.session_state.notice = f"Berhasil: Voucher #{hid} telah diposting secara permanen. Lihat tab Jurnal & pembalik."
            # Reset form key untuk iterasi selanjutnya
            st.session_state.voucher_key = uuid.uuid4().hex[:8].upper()
            st.rerun()
        except Exception as exc:
            st.error(service.error_message(exc))

with stock_tab:
    st.subheader("Mutasi persediaan")
    df_items = pd.DataFrame(all_items)
    if not df_items.empty:
        st.dataframe(df_items.rename(columns={"item_id": "Kode", "item_name": "Barang", "stock_qty": "Stok", "unit_cost": "Biaya/unit", "stock_value": "Nilai stok"}), hide_index=True, width="stretch")
    with st.form("stock_form"):
        a, b, c = st.columns(3)
        item = a.selectbox("Barang", [x["item_id"] for x in all_items])
        kind = b.selectbox("Jenis", ["PURCHASE", "SALE", "ADJUSTMENT"])
        qty = c.number_input("Kuantitas", value=1, step=1)
        ref = st.text_input("Referensi stok", "ST-"+uuid.uuid4().hex[:8].upper(), max_chars=76)
        reason = st.text_input("Keterangan mutasi", "Penerimaan/pengeluaran barang")
        st.caption("PURCHASE/SALE: kuantitas positif. ADJUSTMENT: positif untuk menambah, negatif untuk mengurangi.")
        submit_stock = st.form_submit_button("Catat mutasi", type="primary")
    if submit_stock:
        try:
            tid = service.inventory(item, kind, int(qty), ref, reason)
            st.session_state.notice = f"Mutasi #{tid} tersimpan. Stok dan jurnal diperbarui dalam satu transaksi atomik."
            st.rerun()
        except Exception as exc: 
            st.error(service.error_message(exc))

with journal_tab:
    st.subheader("Jurnal yang diposting")
    if st.button("Muat ulang data", key="refresh"): 
        st.rerun()
        
    if not all_journals:
        st.info("Belum ada jurnal. Buat voucher atau transaksi persediaan pertama.")
    else:
        shown = pd.DataFrame(all_journals)[["id", "transaction_date", "reference_no", "description", "amount", "status_posting", "checksum_valid"]]
        st.dataframe(shown, hide_index=True, width="stretch")
        
        chosen_id = st.selectbox("Periksa detail jurnal", [j["id"] for j in all_journals])
        selected = next(j for j in all_journals if j["id"] == chosen_id)
        st.dataframe(pd.DataFrame(service.journal_lines(chosen_id)), hide_index=True, width="stretch")
        
        st.caption("Sidik jari data (SHA-256 tersimpan)")
        st.code(selected["hash_checksum"] or "Belum diposting", language=None)
        
        already_reversed = any(j["reversal_of"] == chosen_id for j in all_journals)
        if selected["voucher_type"] in ("CASH_OUT", "GENERAL") and not already_reversed:
            with st.expander("Buat jurnal pembalik (Koreksi)"):
                with st.form("reverse_form"):
                    reverse_date = st.date_input("Tanggal pembalik", date.today(), min_value=selected["transaction_date"])
                    reverse_ref = st.text_input("Nomor bukti pembalik", "REV-"+str(chosen_id), max_chars=80)
                    reverse_reason = st.text_input("Alasan pembalikan")
                    confirm = st.checkbox("Saya telah memeriksa jurnal dan yakin membaliknya.")
                    do_reverse = st.form_submit_button("Posting pembalik", type="primary")
                if do_reverse:
                    if not confirm: 
                        st.warning("Centang konfirmasi pemeriksaan terlebih dahulu.")
                    else:
                        try:
                            rid = service.reverse(chosen_id, reverse_date, reverse_ref, reverse_reason)
                            st.session_state.notice = f"Jurnal pembalik #{rid} berhasil dibuat. Jurnal asal tetap dipertahankan."
                            st.rerun()
                        except Exception as exc: 
                            st.error(service.error_message(exc))
        elif already_reversed:
            st.info("Jurnal ini telah dibalik (direverse).")
        else:
            st.caption("Jurnal stok dikoreksi melalui mutasi ADJUSTMENT di tab Persediaan. Jurnal yang sudah dibalik tidak dapat dibalik ulang.")

with audit_tab:
    st.subheader("Jejak audit")
    st.caption("Waktu dalam zona UTC. Modifikasi tabel dicatat melalui trigger database.")
    audit = service.audit()
    if audit:
        st.dataframe(pd.DataFrame(audit)[["audit_id", "event_at", "actor", "table_name", "operation", "row_key", "transaction_id"]], hide_index=True, width="stretch")
        with st.expander("Detail payload JSON (Sebelum dan Sesudah)"):
            event = st.selectbox("Pilih ID peristiwa", [a["audit_id"] for a in audit])
            st.json(next(a for a in audit if a["audit_id"] == event), expanded=False)
    else: 
        st.info("Belum ada peristiwa modifikasi data audit.")