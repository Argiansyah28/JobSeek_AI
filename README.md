---
title: JobSeek AI
emoji: 💼
colorFrom: yellow
colorTo: gray
sdk: gradio
app_file: app.py
pinned: false
short_description: Cari lowongan kerja & magang Jabodetabek, lalu siapkan CV dan draf emailnya.
---

# 🤖 JobSeek AI

Agent pribadi untuk berburu kerja dan magang di **Jakarta, Kota Tangerang, dan
Tangerang Selatan**. Berjalan sebagai **web dashboard**, bukan menu terminal.

Alur kerjanya: cari lowongan → saring per wilayah & mode kerja → analisis
kecocokan dengan CV → sesuaikan CV → siapkan draf email lamaran.

---

## Cara Menjalankan

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

export GEMINI_API_KEY="key-kamu"  # ambil gratis di aistudio.google.com/apikey
python app.py
```

Browser akan terbuka otomatis di <http://127.0.0.1:5000>.
`python main.py` juga tetap bekerja — isinya meneruskan ke `app.py`.

API key **hanya** dibaca dari environment variable, tidak pernah ditulis di
dalam kode. Lihat [`.env.example`](.env.example) untuk daftar variabelnya.

---

## Yang Bisa Dilakukan

### 1. Cari Lowongan
Pilih dulu jenisnya, lalu sistem mencari sesuai kriteria masing-masing:

| Pilihan | Yang dicari |
|---|---|
| 💼 **Lowongan Kerja** | Posisi full time, kontrak, part time |
| 🎓 **Magang / Internship** | Program magang dan internship |

Wilayah dan sumber bisa dicentang sesuai kebutuhan. Hasil di luar wilayah
yang dipilih otomatis dibuang.

### 2. Mode Kerja Ditandai Jelas
Tiap lowongan diberi label:

| Label | Arti |
|---|---|
| 🏠 **WFH / Remote** | Kerja dari rumah |
| 🔀 **Hybrid** | Campuran kantor dan rumah |
| 🏢 **WFO / On-site** | Kerja dari kantor |
| ❔ **Tidak disebutkan** | Sumbernya memang tidak menyebutkan |

Label terakhir itu disengaja: lebih baik jujur tidak tahu daripada menebak asal.

### 3. Proses dengan AI
Klik **"Proses dengan AI"** pada sebuah lowongan, dan agent akan:

1. Mengambil job description lengkap dari situs sumbernya
2. Menganalisis kecocokan CV dengan lowongan (apa yang sudah cocok, apa yang kurang)
3. Mengekstrak kata kunci penting dari job description
4. Menyesuaikan CV agar selaras dengan lowongan tersebut
5. Menyusun draf email lamaran

Semua hasilnya tersimpan otomatis ke folder `output/`.

### 4. Input Manual
Untuk lowongan yang kamu temukan sendiri, atau kalau job description dari
situsnya gagal diambil — tempel isinya, lalu proses seperti biasa.

### 5. Tab CV Saya
Edit isi `my_cv.txt` langsung dari dashboard, tanpa buka text editor.

---

## Sumber Lowongan

| Sumber | Cara ambil | Mode kerja |
|---|---|---|
| **LinkedIn** | Endpoint `jobs-guest` (halaman publik) | Ditebak dari isi job description |
| **JobStreet** | API pencarian + GraphQL `jobDetails` | Disebutkan langsung oleh JobStreet |
| **Glints** | `__NEXT_DATA__` halaman explore | Disebutkan langsung oleh Glints |

**Catatan LinkedIn:** halaman publik LinkedIn tidak menyebut WFH/WFO/Hybrid,
dan filter `f_WT`/`f_E` diabaikan oleh endpoint tamu. Karena itu ada opsi
**"Deteksi mode kerja LinkedIn"** yang membuka halaman detail tiap lowongan
untuk mencari petunjuknya. Lebih akurat, tapi pencarian jadi lebih lama.
Matikan opsi ini kalau ingin hasil cepat.

**Catatan Glints:** Glints memasang firewall yang menolak HTTP client biasa.
Karena itu project ini memakai `curl_cffi`, yang meniru TLS fingerprint Chrome.
Kalau paket ini belum terpasang, sumber Glints akan dilewati dengan pesan jelas
di log, sementara LinkedIn dan JobStreet tetap jalan.

---

## Konfigurasi

Semua di [`config.py`](config.py):

| Yang bisa diubah | Keterangan |
|---|---|
| `GEMINI_MODELS` | Daftar model; dicoba berurutan kalau salah satu bermasalah |
| `LOCATIONS` | Wilayah beserta kata kunci pencocokan lokasinya |
| `JOB_QUERIES` | Kata kunci default untuk pencarian kerja |
| `INTERNSHIP_QUERIES` | Kata kunci default untuk pencarian magang |
| `ENRICH_LINKEDIN` | Deteksi mode kerja LinkedIn, default aktif |
| `LIMIT_PER_QUERY` | Jumlah lowongan per kata kunci per sumber |
| `MY_NAME`, `MY_EMAIL`, `MY_PHONE` | Dipakai di draf email lamaran |

Yang lewat environment variable (bukan `config.py`):

| Variable | Keterangan |
|---|---|
| `GEMINI_API_KEY` | **Wajib.** API key dari <https://aistudio.google.com/apikey> (gratis) |
| `HOST` | Alamat bind. Default `127.0.0.1`; isi `0.0.0.0` saat deploy |
| `PORT` | Default `5000`. Di hosting biasanya diisi otomatis |

---

## Deploy

Project ini menjalankan proses AI yang panjang (sampai ~200 detik per langkah)
di thread latar belakang, dan menyimpan status pencarian di memori proses.
Karena itu **platform serverless seperti Vercel tidak cocok** — fungsinya
berhenti begitu response dikirim, sehingga proses latar belakang terbunuh dan
polling status berikutnya bisa jatuh ke instance lain yang memorinya kosong.

Pakai platform yang menjalankan proses server biasa.

### Hugging Face Spaces (gratis, tanpa kartu kredit)

Repo ini sudah berisi frontmatter Space di atas. Buat Space baru dengan SDK
**Gradio** (SDK Docker sekarang berbayar), lalu isi di tab **Settings**:

| Jenis | Nama | Nilai |
|---|---|---|
| Secret | `GEMINI_API_KEY` | key kamu |
| Variable | `HOST` | `0.0.0.0` |
| Variable | `PORT` | `7860` |

Spaces menjalankan `python app.py`, dan `main()` sudah membaca kedua variable
di atas — jadi tidak ada kode yang perlu diubah. `Dockerfile` di repo ini
tidak dipakai oleh jalur ini; simpan saja untuk platform lain.

### Render

| Pengaturan | Isi |
|---|---|

| Pengaturan | Isi |
|---|---|
| Environment | `Python 3` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 300` |
| Env Var | `GEMINI_API_KEY` = key kamu |
| Env Var | `HOST` = `0.0.0.0` |

Tiga flag di start command itu bukan hiasan:

- **`--workers 1`** — wajib. Status pencarian disimpan di memori proses
  (`_tasks` dan `_last_jobs` di `app.py`). Kalau worker-nya lebih dari satu,
  request polling bisa mendarat di proses lain yang memorinya kosong dan
  dibalas 404. Diuji dengan 2 worker: 10 dari 12 polling gagal.
- **`--threads 4`** — supaya satu proses tadi tetap bisa melayani beberapa
  request sekaligus (polling status sambil scraping jalan).
- **`--timeout 300`** — default gunicorn 30 detik akan memutus proses AI
  di tengah jalan.

Repo ini juga menyertakan [`render.yaml`](render.yaml), jadi kamu bisa pakai
menu **Blueprint** di Render dan semua pengaturan di atas terisi otomatis —
tinggal isi `GEMINI_API_KEY`.

Catatan tier gratis Render: instance tidur setelah ~15 menit tanpa trafik,
dan request pertama sesudahnya butuh ~30–50 detik untuk bangun. File hasil
di `output/` juga hilang tiap redeploy karena filesystem-nya sementara —
unduh hasilnya lewat dashboard kalau mau disimpan.

---

## Struktur Project

```
job-agent/
├── app.py              # Web dashboard (Flask) — titik masuk utama
├── main.py             # Pintasan ke app.py
├── scraper.py          # Menggabungkan semua sumber, menyaring, mengurutkan
├── agent.py            # Gemini: analisis, kata kunci, CV, email
├── config.py           # Semua pengaturan
├── sources/
│   ├── base.py         # HTTP client, deteksi mode kerja, pencocokan lokasi
│   ├── linkedin.py
│   ├── jobstreet.py
│   └── glints.py
├── templates/index.html
├── static/{style.css, app.js}
├── my_cv.txt           # CV kamu (bisa diedit dari dashboard)
└── output/             # Hasil AI tersimpan di sini
```

---

## Cara Kerja Penyaringan

1. **Kumpulkan** — tiap sumber × kata kunci × wilayah dijalankan paralel
2. **Saring lokasi** — hanya Jakarta / Kota Tangerang / Tangerang Selatan yang lolos.
   Situs lowongan sering mengembalikan hasil dari radius 50 km, jadi penyaringan
   ini dikerjakan ulang di sisi kita
3. **Buang duplikat** — satu lowongan sering tayang di dua situs sekaligus;
   sumber tambahannya ditampilkan sebagai badge `+ Glints`
4. **Pisahkan job vs magang** — berdasarkan tipe pekerjaan dari sumber,
   dan kata kunci di judul kalau sumbernya tidak menyebutkan
5. **Skor kecocokan** — hitungan cepat tanpa AI, hanya untuk mengurutkan daftar.
   Penilaian sesungguhnya dikerjakan Gemini saat lowongan diproses

---

## Kalau Ada Masalah

| Gejala | Sebabnya |
|---|---|
| Glints selalu gagal | `curl_cffi` belum terpasang → `pip install curl_cffi` |
| Langkah AI lama sekali | Server Gemini kadang lambat merespons. Tiap langkah dibatasi `GEMINI_TOTAL_BUDGET` (200 detik), lalu berhenti dengan pesan jelas — tidak menggantung selamanya |
| `504 DEADLINE_EXCEEDED` | Model itu sedang tidak responsif. Agent otomatis pindah ke model berikutnya di `GEMINI_MODELS`; kalau semua gagal, coba lagi beberapa menit lagi |
| Model tidak ditemukan (404) | Google mempensiunkan model itu — ganti isi `GEMINI_MODELS` di `config.py` |
| Hasil sedikit | Longgarkan kata kunci, tambah wilayah, atau naikkan `LIMIT_PER_QUERY` |
| JD gagal diambil | Buka link lowongannya, salin isinya, lalu pakai tab **Input Manual** |
