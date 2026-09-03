"""
Scraper Glints Indonesia.

Glints memasang firewall yang menolak HTTP client biasa (selalu HTTP 403),
jadi request-nya lewat curl_cffi yang meniru TLS fingerprint Chrome.

Daftar lowongan diambil dari __NEXT_DATA__ halaman /id/opportunities/jobs/explore
(server-rendered, 30 lowongan sekali muat). Filter lokasi Glints butuh
locationId internal, jadi lokasi disaring di sisi kita lewat hierarki
location.parents yang sudah ikut di payload.
"""

import json
import re
from urllib.parse import urlencode

from . import base
from .base import SourceError

NAME = "Glints"

EXPLORE_URL = "https://glints.com/id/opportunities/jobs/explore"
JOB_URL = "https://glints.com/id/opportunities/jobs/{job_id}"
DETAIL_API = "https://glints.com/api/v2/jobs/{job_id}"

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.S,
)

# Glints -> label mode kerja aplikasi
WORK_MODE_MAP = {
    "ONSITE": base.WFO,
    "HYBRID": base.HYBRID,
    "REMOTE": base.WFH,
}

EMPLOYMENT_MAP = {
    "FULL_TIME": "Full time",
    "PART_TIME": "Part time",
    "INTERNSHIP": "Magang",
    "CONTRACT": "Kontrak",
    "TEMPORARY": "Temporer",
    "PROJECT_BASED": "Project based",
    "DAILY": "Harian",
}


def search(query: str, location_conf: dict, limit: int = 15,
           internship: bool = False) -> list[dict]:
    """
    Cari lowongan di Glints.

    location_conf tidak dipakai untuk query (Glints butuh locationId internal),
    lowongan disaring per wilayah oleh scraper.py memakai teks lokasi hasil.
    """
    params = {"country": "ID", "keyword": query}
    if internship:
        params["jobTypes"] = "INTERNSHIP"

    try:
        resp = base.get_browserlike(f"{EXPLORE_URL}?{urlencode(params)}")
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"gagal akses Glints: {e}") from e

    match = NEXT_DATA_RE.search(resp.text)
    if not match:
        raise SourceError("format halaman Glints berubah (__NEXT_DATA__ tidak ketemu)")

    try:
        page_props = json.loads(match.group(1))["props"]["pageProps"]
        raw_jobs = (page_props.get("initialJobs") or {}).get("jobsInPage") or []
    except (KeyError, ValueError) as e:
        raise SourceError(f"gagal membaca data Glints: {e}") from e

    results = []
    for item in raw_jobs[:limit]:
        company = item.get("company") or {}
        job_id = item.get("id", "")

        results.append(
            base.make_job(
                title=item.get("title", ""),
                company=company.get("brandName") or company.get("name", ""),
                location=_location_text(item),
                url=JOB_URL.format(job_id=job_id) if job_id else "",
                source=NAME,
                work_mode=WORK_MODE_MAP.get(
                    item.get("workArrangementOption", ""), base.UNKNOWN
                ),
                employment_type=EMPLOYMENT_MAP.get(item.get("type", ""), item.get("type", "")),
                salary=_salary_text(item.get("salaries") or []),
                posted=(item.get("createdAt") or "")[:10],
                external_id=job_id,
                skills=[
                    s.get("name", "") for s in (item.get("skills") or []) if s.get("name")
                ],
            )
        )

    return results


def fetch_description(job: dict) -> str:
    """
    Ambil job description lengkap dari Glints.

    Dua jalur, karena API detail Glints membalas HTTP 500 untuk sebagian
    lowongan (kemungkinan lowongan hasil agregasi):
      1. /api/v2/jobs/{id}  -> descriptionRaw.blocks
      2. halaman publik lowongan -> initialData.data.descriptionJsonString
    """
    job_id = job.get("external_id")
    if not job_id:
        return ""

    try:
        resp = base.get_browserlike(DETAIL_API.format(job_id=job_id), timeout=25)
        data = resp.json().get("data") or {}
        blocks = (data.get("descriptionRaw") or {}).get("blocks") or []
        text = _blocks_to_text(blocks)
        if text:
            return text
    except Exception:  # noqa: BLE001 - lanjut ke jalur kedua
        pass

    return _description_from_page(job_id)


def _description_from_page(job_id: str) -> str:
    """Jalur cadangan: baca deskripsi dari __NEXT_DATA__ halaman lowongan."""
    resp = base.get_browserlike(JOB_URL.format(job_id=job_id), timeout=30)

    match = NEXT_DATA_RE.search(resp.text)
    if not match:
        raise SourceError("halaman lowongan Glints tidak bisa dibaca")

    try:
        data = (
            json.loads(match.group(1))["props"]["pageProps"]["initialData"]["data"]
        )
    except (KeyError, ValueError) as e:
        raise SourceError(f"struktur halaman Glints berubah: {e}") from e

    raw = data.get("descriptionJsonString")
    if not raw:
        return ""

    try:
        blocks = json.loads(raw).get("blocks") or []
    except ValueError:
        return ""

    return _blocks_to_text(blocks)


def _blocks_to_text(blocks: list[dict]) -> str:
    """Ubah blok Draft.js milik Glints jadi teks biasa."""
    lines = []
    for block in blocks:
        text = (block.get("text") or "").strip()
        if not text:
            continue
        if block.get("type") in {"unordered-list-item", "ordered-list-item"}:
            lines.append(f"- {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


def _location_text(item: dict) -> str:
    """
    Rangkai lokasi dari hierarki Glints, contoh: "Menteng, Jakarta Pusat, DKI Jakarta".
    Field `city` sering null, jadi hierarki `location.parents` yang diandalkan.
    """
    parts = []
    loc = item.get("location") or {}

    if loc.get("formattedName"):
        parts.append(loc["formattedName"])

    for parent in loc.get("parents") or []:
        if parent.get("formattedName"):
            parts.append(parent["formattedName"])
        for grand in parent.get("parents") or []:
            name = grand.get("formattedName")
            # Level 1 = negara, tidak perlu ditampilkan berulang.
            if name and grand.get("level") != 1:
                parts.append(name)

    if not parts:
        city = item.get("city") or {}
        if city.get("name"):
            parts.append(city["name"])

    # Buang duplikat, pertahankan urutan.
    seen, unique = set(), []
    for p in parts:
        if p.lower() not in seen:
            seen.add(p.lower())
            unique.append(p)

    return ", ".join(unique)


def _salary_text(salaries: list[dict]) -> str:
    """Format gaji Glints jadi teks singkat, contoh: "IDR 9.000.000 - 13.500.000 / bulan"."""
    for sal in salaries:
        lo, hi = sal.get("minAmount"), sal.get("maxAmount")
        if not lo and not hi:
            continue
        cur = sal.get("CurrencyCode", "IDR")
        mode = {"MONTH": "bulan", "YEAR": "tahun", "DAY": "hari", "HOUR": "jam"}.get(
            sal.get("salaryMode", ""), ""
        )
        if lo and hi and lo != hi:
            amount = f"{_rupiah(lo)} - {_rupiah(hi)}"
        else:
            amount = _rupiah(hi or lo)
        return f"{cur} {amount}" + (f" / {mode}" if mode else "")
    return ""


def _rupiah(n) -> str:
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)
