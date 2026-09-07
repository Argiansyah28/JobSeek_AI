"""
Utilitas yang dipakai bersama oleh semua sumber lowongan:
HTTP client, normalisasi mode kerja (WFH/WFO/Hybrid), dan pencocokan lokasi.
"""

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from config import LOCATIONS, LOCATION_ORDER, INTERNSHIP_HINTS

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

# === Label mode kerja yang dipakai di seluruh aplikasi ===
WFH = "WFH"          # Work From Home / Remote
WFO = "WFO"          # Work From Office / On-site
HYBRID = "Hybrid"
UNKNOWN = "Tidak disebutkan"


class SourceError(Exception):
    """Sumber gagal diakses (diblokir, timeout, dsb)."""


def get_html(url: str, timeout: int = 20) -> str:
    """GET biasa pakai requests. Untuk situs yang tidak pakai anti-bot ketat."""
    import requests

    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def get_json(url: str, timeout: int = 20) -> dict:
    """GET JSON pakai requests."""
    import requests

    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def get_browserlike(url: str, timeout: int = 30):
    """
    GET dengan TLS fingerprint browser asli (curl_cffi).
    Dibutuhkan Glints, yang menolak HTTP client biasa dengan halaman firewall.
    """
    try:
        from curl_cffi import requests as cr
    except ImportError as e:
        raise SourceError(
            "Butuh paket 'curl_cffi'. Jalankan: pip install curl_cffi"
        ) from e

    resp = cr.get(url, impersonate="chrome", timeout=timeout, headers={
        "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
    })
    if resp.status_code == 403:
        raise SourceError("Diblokir firewall situs (HTTP 403)")
    resp.raise_for_status()
    return resp


def clean_html(html_text: str) -> str:
    """Buang tag HTML, sisakan teks rapi."""
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text(separator="\n", strip=True)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def detect_work_mode(*texts: str) -> str:
    """
    Tebak mode kerja dari teks bebas (judul + lokasi + deskripsi).
    Dipakai untuk LinkedIn, yang tidak memberi field mode kerja di halaman publik.
    """
    blob = " ".join(t for t in texts if t).lower()

    if re.search(r"\bhybrid\b|\bhibrida\b|hybrid working|kerja hybrid", blob):
        return HYBRID
    if re.search(
        r"\bremote\b|\bwfh\b|work from home|kerja dari rumah|fully remote|"
        r"remote[- ]first|jarak jauh",
        blob,
    ):
        return WFH
    if re.search(
        r"\bon[- ]?site\b|\bwfo\b|work from office|di kantor|"
        r"kerja dari kantor|onsite",
        blob,
    ):
        return WFO
    return UNKNOWN


def normalize_work_mode(raw: str) -> str:
    """
    Ubah label mode kerja bawaan situs jadi label standar aplikasi.
    Menangani label Indonesia (JobStreet) dan konstanta Inggris (Glints).
    """
    if not raw:
        return UNKNOWN
    v = raw.strip().lower()

    if v in {"hybrid", "hibrida"} or "hybrid" in v or "hibrida" in v:
        return HYBRID
    if v in {"remote", "wfh"} or "remote" in v or "jarak jauh" in v or "rumah" in v:
        return WFH
    if v in {"onsite", "on-site", "on site", "kantor", "wfo"} or "kantor" in v or "site" in v:
        return WFO
    return UNKNOWN


def match_location(*texts: str) -> tuple[str, str] | tuple[None, None]:
    """
    Cek apakah lokasi lowongan masuk wilayah yang kita incar.
    Return (location_key, label) kalau cocok, (None, None) kalau di luar wilayah.

    Urutan pengecekan mengikuti LOCATION_ORDER supaya "Tangerang Selatan"
    tidak keburu tertangkap oleh aturan "Kota Tangerang".
    """
    blob = " ".join(t for t in texts if t).lower()
    if not blob.strip():
        return None, None

    for key in LOCATION_ORDER:
        for needle in LOCATIONS[key]["match"]:
            if needle in blob:
                return key, LOCATIONS[key]["label"]

    # "Tangerang" polos tanpa embel-embel dianggap Kota Tangerang.
    if "tangerang" in blob:
        return "kota_tangerang", LOCATIONS["kota_tangerang"]["label"]

    return None, None


def parse_date(value: str) -> date | None:
    """
    Ubah tanggal dari sumber mana pun jadi objek date yang bisa dibandingkan.

    Bentuk yang ditemui di lapangan:
      LinkedIn  -> "2026-09-01"                  (atribut datetime)
      JobStreet -> "2026-08-28T10:02:12Z"        (ISO dengan zona waktu)
      Glints    -> "2026-08-18T03:28:50.895Z"    (ISO dengan milidetik)

    Return None kalau tidak bisa dibaca — pemanggil yang memutuskan
    bagaimana memperlakukan lowongan tanpa tanggal.
    """
    if not value:
        return None

    text = value.strip()
    # fromisoformat baru mengenal "Z" di Python 3.11+; ini menjaga
    # supaya tetap jalan kalau nanti dipakai di versi yang lebih lama.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass

    # Cadangan: ambil bagian YYYY-MM-DD dari depan teks.
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        try:
            return date(*(int(g) for g in match.groups()))
        except ValueError:
            return None

    return None


def looks_like_internship(*texts: str) -> bool:
    """Cek apakah sebuah lowongan kemungkinan besar magang."""
    blob = " ".join(t for t in texts if t).lower()
    return any(hint in blob for hint in INTERNSHIP_HINTS)


def make_job(
    *,
    title: str,
    company: str,
    location: str,
    url: str,
    source: str,
    work_mode: str = UNKNOWN,
    employment_type: str = "",
    salary: str = "",
    posted: str = "",
    posted_at: str = "",
    teaser: str = "",
    external_id: str = "",
    skills: list[str] | None = None,
) -> dict:
    """
    Bentuk satu record lowongan dengan struktur yang seragam antar sumber.

    `posted`    : teks apa adanya untuk ditampilkan ("5 hari yang lalu")
    `posted_at` : tanggal ISO untuk disaring dan diurutkan ("2026-08-28")
    Keduanya dipisah karena tiap situs menampilkan tanggal dengan gaya
    berbeda, sementara pengurutan butuh format yang seragam.
    """
    return {
        "title": (title or "").strip(),
        "company": (company or "").strip(),
        "location": (location or "").strip(),
        "url": url or "",
        "source": source,
        "work_mode": work_mode,
        "employment_type": employment_type,
        "salary": salary,
        "posted": posted,
        "posted_at": posted_at,
        "teaser": teaser,
        "external_id": str(external_id),
        "skills": skills or [],
        # Diisi belakangan oleh scraper / dashboard:
        "location_key": "",
        "location_label": "",
        "description": "",
    }
