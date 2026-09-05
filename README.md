# 🤖 JobSeek AI

Agent pribadi untuk berburu kerja dan magang di **Jakarta, Kota Tangerang, dan
Tangerang Selatan**. Berjalan sebagai **web dashboard**, bukan menu terminal.

Alur kerjanya: cari lowongan → saring per wilayah & mode kerja → analisis
kecocokan dengan CV → sesuaikan CV → siapkan draf email lamaran.

---

## Cara Menjalankan

```bash
python -m venv venv
source venv/bin/activate          
pip install -r requirements.txt

export GEMINI_API_KEY="key-kamu"  
python app.py
```

Browser akan terbuka otomatis di <http://127.0.0.1:5000>.
`python main.py` juga tetap bekerja — isinya meneruskan ke `app.py`.

API key hanya dibaca dari environment variable, tidak pernah ditulis di
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





