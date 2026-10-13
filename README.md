# Paket UTS Pemrograman Akuntansi

Zidan Anargya Elian Mulyono · NIM 12030124130141

Proyek berisi jawaban tiga soal: skema jurnal, trigger persediaan, serta voucher kas keluar dengan Streamlit, FastAPI, dan PostgreSQL. Baca `docs/jawaban.md` atau PDF untuk penjelasan. Aplikasi menyimpan transaksi sungguhan ke database proyek; tidak ada mode penyimpanan palsu di browser.

## Mulai dari sini

1. Ekstrak ZIP, buka folder proyek ini di terminal.
2. Siapkan Python 3.12.
3. Buat lingkungan Python:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

4. Jalankan aplikasi. Paket ini sudah terhubung ke proyek Supabase UTS melalui Project URL dan anon key pada `.streamlit/secrets.toml`; tidak perlu mengisi password database.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Buka `http://localhost:8501`. Skema `accounting` dan adapter Data API sudah terpasang pada proyek `UTS Akuntansi Zidan` (ref `mkbmblsxtmtcdsjqbhke`).

Untuk memasang pada proyek Supabase lain, jalankan SQL 001, 002, 003, 004, dan 007 berurutan, lalu ganti dua nilai pada `.streamlit/secrets.toml`.

Koneksi PostgreSQL langsung melalui `DATABASE_URL` tetap didukung sebagai alternatif untuk instalasi lokal.

## Supabase

Aplikasi memakai Supabase Data API melalui fungsi RPC tervalidasi. Tabel `accounting` tidak diberi izin tulis langsung kepada role `anon`; transaksi hanya bisa masuk lewat fungsi yang memeriksa jurnal seimbang, stok, posting, pembalikan, dan audit. Anon key memang aman disertakan pada aplikasi klien, sedangkan service-role key dan password database tidak disimpan dalam paket.

## Demo singkat

1. Pada Kas keluar, pilih debit Beban perlengkapan kantor Rp250.000 dan kredit Bank Rp250.000. Isi nomor bukti unik, lalu Submit.
2. Ubah salah satu sisi menjadi Rp200.000. Selisih Rp50.000 muncul dan Submit nonaktif.
3. Pada Persediaan, catat PURCHASE 2 unit BRG001. Stok bertambah 2, jurnal debit Persediaan/kredit Utang dibuat Rp50.000.
4. Catat SALE 1 unit. Stok menjadi 1 dan jurnal debit HPP/kredit Persediaan dibuat Rp25.000. SALE 2 unit berikutnya ditolak.
5. Pada Jurnal & pembalik, pilih voucher kas, lihat checksum, lalu isi alasan dan buat pembalik. Jurnal asal tetap POSTED, pasangan debit/kredit ditukar pada jurnal baru.
6. Lihat Jejak audit untuk aktor, waktu, transaksi database, serta data sebelum/sesudah.

Stok awal barang nol; gunakan PURCHASE untuk saldo demo. Harga pokok per unit tetap sesuai `inventory_items.unit_cost`. PURCHASE diasumsikan pembelian kredit; SALE hanya jurnal biaya/HPP, bukan pengakuan pendapatan karena harga jual tidak diberikan. ADJUSTMENT memakai kuantitas bertanda. Akun persediaan tidak boleh diubah dari voucher kas agar fisik dan nilai tetap sinkron. Untuk pembelian tunai, catat PURCHASE kredit kemudian voucher debit Utang/kredit Kas.

## API FastAPI opsional

Streamlit sudah menggunakan backend Python yang sama melalui `backend/service.py`; server HTTP tidak wajib berjalan untuk UI.

```powershell
$env:API_TOKEN='ISI_TOKEN_ACAK_YANG_PANJANG'
.\.venv\Scripts\python.exe -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

Endpoint: `POST /vouchers`, `POST /inventory`, `POST /journals/{id}/reverse`, `GET /journals`, `GET /journals/{id}/integrity`. Header wajib: `Authorization: Bearer <API_TOKEN>`. `PUT`/`DELETE /journals/{id}` ditolak dengan 405. Spesifikasi interaktif di `/docs`. Token demo mengidentifikasi aplikasi satu pengguna, bukan identitas multiuser. `created_by` mencatat login database asli.

## Pengujian

Jangan jalankan tes database pada database yang berisi data penting: tes menambahkan akun transaksi/barang uji. Buat database uji baru dengan instalasi yang sama, serta login aplikasi berprivilege terbatas.

```powershell
$env:TEST_ADMIN_DATABASE_URL='postgresql://ADMIN:PASSWORD@localhost:5432/uts_test'
$env:TEST_DATABASE_URL='postgresql://zidan_uts:PASSWORD@localhost:5432/uts_test'
.\.venv\Scripts\python.exe scripts/run_tests.py
```

Laporan mesin: `docs/hasil_uji.json`. Tanpa kedua environment variable, tes integrasi akan ditandai SKIP, bukan lulus. Uji dua kasir memakai dua koneksi PostgreSQL dan memeriksa wait_event_type Lock sebelum kasir pertama commit. Contoh manual tersedia dalam `sql/005_concurrency_demo.sql`.

## Bukti AI dan pengumpulan

1. Bukti Gemini Canvas, NotebookLM, serta ringkasan verifikasi berada di `docs/bukti_ai/`.
2. Bukti pemasangan dan uji SQL Supabase berada di `docs/supabase_schema.png`, `docs/supabase_hasil_uji.png`, dan `docs/hasil_uji_cloud.json`.
3. Folder Drive pengumpulan tercantum di `submission.json` dan halaman pertama PDF. ZIP tidak memuat `.venv`, `.env`, secret, password, atau data uji lokal.
4. Serahkan tautan kepada komting. Rekap dikumpulkan komting paling lambat 15 menit setelah ujian selesai, sesuai naskah.

## Membuat ulang PDF

```powershell
.\.venv\Scripts\python.exe -m pip install reportlab
.\.venv\Scripts\python.exe scripts/build_pdf.py
```

Sumber narasi `docs/jawaban.md` dapat diedit. PDF keluaran berada di direktori proyek. Untuk memperbarui uraian NotebookLM, edit bagian terkait berdasarkan hasil sesi asli dan bangun ulang PDF. Template AcroForm hanya untuk tautan, bukan untuk mengisi narasi panjang.

## Isi proyek

- `sql/`: skema, aturan bisnis, seed, permission, skenario concurrency.
- `app.py`: UI Streamlit.
- `backend/`: koneksi, validasi, layanan transaksi, API HTTP.
- `tests/` dan `scripts/run_tests.py`: uji otomatis serta laporan JSON.
- `docs/`: jawaban yang bisa diedit, ERD SVG, sumber, prompt dan bukti.
- `scripts/build_pdf.py`: generator PDF dari jawaban dan kode proyek.
- `submission.json`: metadata dan URL pengumpulan.

Pemisahan DRAFT/POSTED merupakan kebijakan kontrol aplikasi; hanya POSTED masuk buku besar. Hash SHA-256 membantu mendeteksi perubahan isi tetapi bukan tanda tangan digital. Pemilik database/superuser dapat mengubah aturan atau hash; perlindungan terhadap administrator membutuhkan cadangan/log eksternal yang dikelola terpisah.
