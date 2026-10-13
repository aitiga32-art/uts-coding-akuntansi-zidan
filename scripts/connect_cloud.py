"""Form setup lokal: password hanya di memori; tidak ditulis ke artefak.
Jalankan: python -m streamlit run scripts/connect_cloud.py --server.port 8502
"""
from pathlib import Path
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import streamlit as st

ROOT=Path(__file__).resolve().parents[1]
HOST='aws-0-ap-northeast-1.pooler.supabase.com'
REF='mkbmblsxtmtcdsjqbhke'
ROLE='zidan_uts'
st.set_page_config(page_title='Hubungkan UTS ke Supabase',page_icon='🔒')
st.title('Hubungkan aplikasi UTS ke Supabase')
st.write('Khusus proyek UTS Akuntansi Zidan. Form berjalan di komputer ini (localhost).')
st.caption('Koneksi terenkripsi ke Supabase. Password tidak dicatat dalam laporan, ZIP, atau file konfigurasi.')

if st.session_state.get('ready'):
    st.success('Koneksi pengguna aplikasi berhasil. Hak akses terbatas sudah diverifikasi.')
    st.link_button('Buka aplikasi voucher', 'http://localhost:8501')
    st.info('Biarkan proses aplikasi berjalan selama demo. Tutup terminal aplikasi untuk menghentikannya.')
    st.stop()

st.info('Pertama kali: isi password database proyek dan buat password login aplikasi yang berbeda. Jika login aplikasi sudah dibuat, gunakan mode Hubungkan login yang sudah ada.')
mode=st.radio('Mode', ['Buat login aplikasi baru','Hubungkan login yang sudah ada'])
with st.form('cloud_setup',clear_on_submit=True):
    admin_password=st.text_input('Password database proyek Supabase (admin)',type='password') if mode=='Buat login aplikasi baru' else ''
    app_password=st.text_input('Password login aplikasi zidan_uts',type='password')
    confirm_password=st.text_input('Ulangi password login aplikasi',type='password')
    consent=st.checkbox('Saya setuju menghubungkan aplikasi lokal ke proyek UTS ini dengan hak akses terbatas.')
    submitted=st.form_submit_button('Hubungkan dan buka aplikasi',type='primary')

if submitted:
    if not consent or app_password!=confirm_password or len(app_password)<16:
        st.error('Centang persetujuan dan gunakan password aplikasi minimal 16 karakter yang sama pada kedua kolom.')
        st.stop()
    if mode=='Buat login aplikasi baru' and (not admin_password or admin_password==app_password):
        st.error('Isi password admin dan gunakan password aplikasi yang berbeda.')
        st.stop()
    try:
        if mode=='Buat login aplikasi baru':
            admin_conn=make_conninfo(host=HOST,port=5432,dbname='postgres',user='postgres.'+REF,password=admin_password,sslmode='require',connect_timeout=10)
            with psycopg.connect(admin_conn) as conn:
                if conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(ROLE,)).fetchone():
                    st.error('Login zidan_uts sudah ada. Tidak ada password yang diubah. Gunakan mode login yang sudah ada.')
                    st.stop()
                conn.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION').format(sql.Identifier(ROLE),sql.Literal(app_password)))
                conn.execute(sql.SQL('GRANT uts_accounting_app TO {}').format(sql.Identifier(ROLE)))
        app_conn=make_conninfo(host=HOST,port=5432,dbname='postgres',user=ROLE+'.'+REF,password=app_password,sslmode='require',connect_timeout=10)
        with psycopg.connect(app_conn) as conn:
            actor,version=conn.execute("SELECT session_user,current_setting('server_version')").fetchone()
            accounts=conn.execute('SELECT count(*) FROM accounting.chart_of_accounts').fetchone()[0]
            can_update=conn.execute("SELECT has_table_privilege(current_user,'accounting.journal_headers','UPDATE')").fetchone()[0]
            can_submit=conn.execute("SELECT has_function_privilege(current_user,'accounting.submit_cash_voucher(date,text,text,jsonb)','EXECUTE')").fetchone()[0]
            if actor!=ROLE or can_update or not can_submit or accounts<2:
                raise RuntimeError('Hak akses tidak sesuai')
        report={'status':'PASS','project_ref':REF,'host':HOST,'server_version':version,
            'session_user':actor,'accounts':accounts,'direct_header_update_allowed':can_update,
            'submit_voucher_allowed':can_submit,'executed_at':datetime.now(timezone.utc).isoformat(),
            'scope':'Koneksi Python melalui session pooler dengan login aplikasi terbatas'}
        (ROOT/'docs'/'hasil_koneksi_cloud.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        child_env=os.environ.copy(); child_env['DATABASE_URL']=app_conn
        child=subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT/'app.py'),'--server.port','8501','--server.address','127.0.0.1','--server.headless','true'],cwd=ROOT,env=child_env,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        st.session_state['ready']=True
        st.session_state['app_pid']=child.pid
        st.rerun()
    except (psycopg.Error,RuntimeError,OSError):
        st.error('Koneksi atau konfigurasi belum berhasil. Periksa password dan jaringan. Detail kredensial sengaja tidak ditampilkan.')
