# Catatan penggunaan bantuan AI

Nama: Zidan Anargya Elian Mulyono
NIM: 12030124130141

## Interaksi yang benar-benar terjadi

Tanggal penyusunan: 13 Oktober 2026. Alat: Codex dalam percakapan ini.

1. Pengguna memberikan naskah UTS dan meminta penjelasan tugas dengan pesan “itu disuruh apa ya”.
2. Pengguna menanyakan bantuan pembuatan paket dan meminta konfirmasi lebih dahulu.
3. Setelah rencana Streamlit + PostgreSQL/Supabase disampaikan, pengguna memberikan nama/NIM dan pesan “Lanjut paket lengkap”; kelas diminta tidak dicantumkan.
4. Codex menyusun SQL, aplikasi Streamlit, backend FastAPI, pengujian, dokumentasi, dan PDF. Sumber teknis/akuntansi yang digunakan dicatat di `referensi.md`.
5. Uji otomatis dan pemeriksaan browser dilakukan pada PostgreSQL lokal terpisah. Hasil mesin dicatat pada `hasil_uji.json`.

## Prompt untuk tahap Gemini Canvas dan NotebookLM

Prompt dalam `prompt_gemini_canvas.txt` dan `prompt_notebooklm.txt` merupakan materi siap digunakan. File ini tidak mengklaim bahwa prompt tersebut sudah dijalankan di kedua layanan tersebut.

Tambahkan ke folder `bukti_ai/` setelah menjalankan sesi:

- Tanggal sesi, nama alat, prompt persis yang dikirim, serta respons asli.
- Ekspor atau tangkapan layar Gemini Canvas yang menunjukkan rancangan formulir.
- Respons NotebookLM dengan sitasi sumber; koreksi yang diterapkan atau alasan tidak menerapkannya.
- Catatan perbedaan hasil AI dan hasil pengujian nyata.

Jangan menyebut analisis persiapan sebagai keluaran NotebookLM. Tinjau setiap jawaban AI dan pahami kode sebelum menjelaskan hasil kepada dosen.
