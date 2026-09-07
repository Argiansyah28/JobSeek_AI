"""
Scraper LinkedIn lewat endpoint "jobs-guest" (halaman publik, tanpa login).

Catatan penting soal mode kerja:
LinkedIn versi publik TIDAK memberi field WFH/WFO/Hybrid, dan filter f_WT
diabaikan oleh endpoint guest. Jadi mode kerja di sini ditebak dari teks
judul + lokasi + deskripsi. Kalau tidak ketemu petunjuk, ditandai
"Tidak disebutkan" — bukan ditebak asal.
"""

import html as html_lib
import re
import time
from urllib.parse import quote

from bs4 import BeautifulSoup

from . import base
from .base import SourceError

NAME = "LinkedIn"

SEARCH_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    "?keywords={keywords}&location={location}&start={start}"
)
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"


def search(query: str, location_conf: dict, limit: int = 15) -> list[dict]:
    """Cari lowongan di LinkedIn untuk satu kata kunci dan satu wilayah."""
    jobs = []
    location = location_conf["linkedin"]

    # Tiap halaman berisi 10 kartu.
    for start in range(0, max(limit, 1), 10):
        url = SEARCH_URL.format(
            keywords=quote(query),
            location=quote(location),
            start=start,
        )
        try:
            html = base.get_html(url)
        except Exception as e:
            if start == 0:
                raise SourceError(f"gagal akses LinkedIn: {e}") from e
            break

        page = _parse_cards(html)
        if not page:
            break
        jobs.extend(page)

        if len(jobs) >= limit:
            break
        time.sleep(0.7)

    return jobs[:limit]


def _parse_cards(html: str) -> list[dict]:
    """Ambil kartu lowongan dari fragmen HTML hasil endpoint guest."""
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for card in soup.select("div.base-card, li div.base-search-card"):
        title_el = card.select_one(".base-search-card__title")
        company_el = card.select_one(".base-search-card__subtitle")
        location_el = card.select_one(".job-search-card__location")
        link_el = card.select_one("a.base-card__full-link")
        date_el = card.select_one("time")

        if not title_el:
            continue

        title = _text(title_el)
        company = _text(company_el)
        location = _text(location_el)
        url = link_el.get("href", "") if link_el else ""
        url = url.split("?")[0]

        # LinkedIn menaruh tanggal ISO di atribut datetime, dan teks
        # perkiraannya ("2 weeks ago") di isi elemen.
        posted_at = date_el.get("datetime", "") if date_el else ""
        posted = posted_at or _text(date_el)

        job_id = ""
        urn = card.get("data-entity-urn", "")
        if urn:
            job_id = urn.rsplit(":", 1)[-1]
        elif url:
            m = re.search(r"-(\d+)$", url)
            job_id = m.group(1) if m else ""

        results.append(
            base.make_job(
                title=title,
                company=company,
                location=location,
                url=url,
                source=NAME,
                # Tebakan awal dari judul + lokasi; diperbaiki kalau JD diambil.
                work_mode=base.detect_work_mode(title, location),
                posted=posted,
                posted_at=posted_at,
                external_id=job_id,
            )
        )

    return results


def fetch_description(job: dict) -> str:
    """Ambil job description lengkap dari halaman detail publik LinkedIn."""
    job_id = job.get("external_id")
    if not job_id:
        return ""

    html = base.get_html(DETAIL_URL.format(job_id=job_id), timeout=25)
    soup = BeautifulSoup(html, "html.parser")

    body = (
        soup.select_one(".description__text .show-more-less-html__markup")
        or soup.select_one(".show-more-less-html__markup")
        or soup.select_one(".description__text")
    )
    parts = []
    if body:
        parts.append(body.get_text(separator="\n", strip=True))

    # Kriteria pekerjaan (Seniority level, Employment type, dst).
    for item in soup.select(".description__job-criteria-item"):
        head = item.select_one(".description__job-criteria-subheader")
        val = item.select_one(".description__job-criteria-text")
        if head and val:
            parts.append(f"{_text(head)}: {_text(val)}")

    text = "\n".join(p for p in parts if p)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _text(el) -> str:
    if el is None:
        return ""
    return html_lib.unescape(el.get_text(strip=True))
