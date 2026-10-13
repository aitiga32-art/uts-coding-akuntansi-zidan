"""Instalasi non-destruktif: menolak jika skema accounting sudah ada."""
import os
from pathlib import Path
import psycopg

root=Path(__file__).resolve().parents[1]
url=os.environ.get("ADMIN_DATABASE_URL")
if not url:
    raise SystemExit("Atur ADMIN_DATABASE_URL untuk database proyek baru.")
with psycopg.connect(url,autocommit=True) as conn:
    if conn.execute("SELECT 1 FROM pg_namespace WHERE nspname='accounting'").fetchone():
        raise SystemExit("Skema accounting sudah ada. Tidak ada data yang dihapus. Gunakan database baru.")
    for name in ["001_schema.sql","002_business_logic.sql","003_seed.sql","004_permissions.sql"]:
        conn.execute((root/"sql"/name).read_text(encoding="utf-8"))
        print("OK",name)
print("Buat login aplikasi, berikan grup uts_accounting_app, lalu atur DATABASE_URL.")
