BEGIN;
INSERT INTO accounting.chart_of_accounts(account_code,account_name,normal_balance,report_class,is_cash) VALUES
('1101','Kas','D','ASSET',true),('1102','Bank','D','ASSET',true),
('1103','Persediaan barang dagang','D','ASSET',false),
('1201','Peralatan','D','ASSET',false),('2101','Utang usaha','C','LIABILITY',false),
('3101','Modal','C','EQUITY',false),('4101','Pendapatan penjualan','C','REVENUE',false),
('5101','Harga pokok penjualan','D','EXPENSE',false),
('5102','Selisih persediaan','D','EXPENSE',false),
('6101','Beban perlengkapan kantor','D','EXPENSE',false),
('6102','Beban listrik','D','EXPENSE',false);
INSERT INTO accounting.inventory_items(item_id,item_name,unit_cost)
VALUES('BRG001','Buku catatan',25000),('BRG002','Kertas A4',55000);
COMMIT;
