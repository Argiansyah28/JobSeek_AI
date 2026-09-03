"""
Konfigurasi JobSeek AI.
Dapatkan API key gratis di https://aistudio.google.com/apikey
"""

import os
from pathlib import Path


def _load_dotenv() -> None:
    """
    Baca file .env kalau ada, tanpa perlu paket tambahan.
    Environment variable yang sudah diset di shell tetap menang, supaya
    di hosting (Render) nilai dari dashboard tidak tertimpa file .env.
    """
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        return

    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_dotenv()

# === API KEY (GRATIS) ===
# Sengaja HANYA dibaca dari environment variable, tidak pernah ditulis di
# file ini. Repo ini publik — API key yang ter-commit harus dianggap bocor
# selamanya, karena tetap tersimpan di riwayat git meski dihapus kemudian.
#
# Cara mengisi:
#   Lokal   : taruh di file .env (lihat .env.example) — .env sudah di-gitignore
#   Render  : tambahkan sebagai Environment Variable di dashboard
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Model Gemini. Kandidat dicoba berurutan sampai ada yang berhasil,
# supaya project tetap jalan kalau satu model dipensiunkan Google.
GEMINI_MODELS = [
    "gemini-flash-latest",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
]

# Batas waktu satu permintaan ke Gemini (detik). Tanpa ini, koneksi yang
# menggantung bisa membuat proses menunggu tanpa batas.
GEMINI_TIMEOUT = 90

# Batas waktu total untuk satu langkah AI, termasuk semua percobaan ulang
# dan pergantian model. Menjaga dashboard tidak menggantung berlama-lama
# saat server Gemini sedang tidak responsif.
GEMINI_TOTAL_BUDGET = 200

# === WILAYAH PENCARIAN (khusus Jabodetabek bagian barat) ===
# key   : id internal, dipakai checkbox di dashboard
# label : nama yang tampil di dashboard
# linkedin / jobstreet : string lokasi sesuai bahasa masing-masing situs
# match : kata kunci untuk memvalidasi lokasi hasil scraping (huruf kecil semua)
LOCATIONS = {
    "tangerang_selatan": {
        "label": "Tangerang Selatan",
        "linkedin": "South Tangerang, Banten, Indonesia",
        "jobstreet": "Tangerang Selatan",
        "match": [
            "tangerang selatan", "south tangerang", "tangsel",
            "bsd", "serpong", "pamulang", "ciputat", "bintaro",
            "pondok aren", "setu", "alam sutera",
        ],
    },
    "kota_tangerang": {
        "label": "Kota Tangerang",
        "linkedin": "Tangerang, Banten, Indonesia",
        # JobStreet tidak mengenal "Kota Tangerang"; "Tangerang" yang benar.
        "jobstreet": "Tangerang",
        "match": [
            "kota tangerang", "tangerang, banten", "tangerang city",
            "cipondoh", "karawaci", "cikokol", "batuceper", "neglasari",
            "periuk", "jatiuwung", "benda", "larangan", "karang tengah",
            "cileduk", "ciledug", "gading serpong",
        ],
    },
    "jakarta": {
        "label": "Jakarta",
        "linkedin": "Jakarta, Indonesia",
        "jobstreet": "Jakarta Raya",
        "match": [
            "jakarta", "dki jakarta", "jakarta raya", "jabodetabek",
            "jakarta pusat", "jakarta utara", "jakarta barat",
            "jakarta selatan", "jakarta timur", "kelapa gading",
            "sudirman", "kuningan", "scbd", "menteng", "kebayoran",
        ],
    },
}

# Urutan pengecekan lokasi. "tangerang selatan" harus dicek sebelum
# "kota tangerang" karena keduanya sama-sama mengandung kata "tangerang".
LOCATION_ORDER = ["tangerang_selatan", "kota_tangerang", "jakarta"]

# === KRITERIA PENCARIAN ===
# Dipakai saat kamu menekan tombol "Cari Lowongan Kerja" di dashboard.
JOB_QUERIES = [
    "full stack developer",
    "frontend developer react",
    "backend developer golang",
    "ai engineer",
    "software engineer",
]

# Dipakai saat kamu menekan tombol "Cari Magang / Internship".
INTERNSHIP_QUERIES = [
    "internship software engineer",
    "magang web developer",
    "frontend developer intern",
    "ai engineer intern",
    "internship it",
]

# Kata yang menandakan sebuah lowongan benar-benar magang.
INTERNSHIP_HINTS = [
    "intern", "internship", "magang", "apprentice", "trainee",
    "mahasiswa", "fresh graduate program", "management trainee",
]

# === SUMBER ===
SOURCES = ["linkedin", "jobstreet", "glints"]

# Berapa lowongan diambil per kata kunci per sumber.
LIMIT_PER_QUERY = 15

# Ambil halaman detail LinkedIn untuk mendeteksi mode kerja & tipe pekerjaan.
# LinkedIn tidak menyebut WFH/WFO/Hybrid di hasil pencarian, jadi tanpa ini
# lowongan LinkedIn akan banyak bertanda "Tidak disebutkan".
# Lebih akurat, tapi pencarian jadi lebih lama.
ENRICH_LINKEDIN = True

# Batas jumlah halaman detail yang diambil sekali cari, supaya tidak
# dianggap abuse oleh LinkedIn.
ENRICH_LIMIT = 60

# Kata yang terlalu umum untuk dipakai menilai kecocokan CV dengan lowongan.
GENERIC_TERMS = {
    "developer", "development", "engineer", "engineering", "programmer",
    "software", "web", "senior", "junior", "middle", "staff", "lead",
    "specialist", "officer", "analyst", "consultant", "manager", "technology",
    "teknologi", "it", "ti", "pt", "cv", "tbk", "remote", "hybrid", "onsite",
    "wfh", "wfo", "jakarta", "tangerang", "banten", "indonesia", "selatan",
    "utara", "barat", "timur", "pusat", "full", "time", "part", "intern",
    "internship", "magang", "kerja", "lowongan", "perusahaan", "kandidat",
    "posisi", "tim", "team", "and", "the", "for", "with", "you", "are", "our",
    "will", "dan", "yang", "untuk", "dengan", "dari", "atau", "pada", "job",
    "work", "min", "max", "tahun", "years", "experience", "pengalaman",
}

# === DATA PRIBADI (untuk email lamaran) ===
MY_NAME = "Argiansyah Galih Permata"
MY_EMAIL = "argiansyahgp@gmail.com"
MY_PHONE = "+6287744415996"

# === FILE ===
CV_FILE = "my_cv.txt"
OUTPUT_DIR = "output"
