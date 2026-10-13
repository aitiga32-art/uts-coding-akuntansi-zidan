-- Dua terminal psql, database uji, barang baru RACE001 (stok awal 0).
-- Administrator: INSERT INTO accounting.inventory_items VALUES('RACE001','Uji',0,10000);
-- SELECT accounting.record_inventory('RACE001','PURCHASE',1,'RACE-OPEN','Stok awal');

-- SESI A: jalankan bagian ini, lalu biarkan transaksi terbuka sementara.
BEGIN;
SELECT accounting.record_inventory('RACE001','SALE',1,'RACE-A','Kasir A');
-- SESI B: sebelum A COMMIT, jalankan BEGIN + SALE di bawah pada terminal lain.
-- Setelah B terlihat menunggu, jalankan:
COMMIT;

-- SESI B (salin hanya bagian ini ke terminal kedua):
-- BEGIN;
-- SELECT accounting.record_inventory('RACE001','SALE',1,'RACE-B','Kasir B');
-- Menunggu lock A; setelah A commit, error stok tidak cukup.
-- ROLLBACK;

-- Stok akhir 0 dan hanya satu SALE tersimpan.
SELECT item_id,stock_qty FROM accounting.inventory_items WHERE item_id='RACE001';
-- Alternatif SERIALIZABLE: retry seluruh transaksi saat SQLSTATE 40001;
-- juga tangani 40P01 (deadlock). Jangan retry kesalahan stok/validasi tanpa perubahan input.
