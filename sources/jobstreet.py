"""
Scraper JobStreet Indonesia (id.jobstreet.com).

Dua endpoint publik yang dipakai:
  - /api/jobsearch/v5/search  -> daftar lowongan (JSON), sudah termasuk
    workArrangements (Kantor / Hibrida / Jarak jauh) dan workTypes.
  - /graphql (query jobDetails) -> isi job description lengkap.

Halaman HTML JobStreet diproteksi anti-bot, jadi jangan di-scrape langsung;
dua endpoint di atas yang dipakai.
"""

from urllib.parse import urlencode

from . import base
from .base import SourceError

NAME = "JobStreet"

SEARCH_URL = "https://id.jobstreet.com/api/jobsearch/v5/search"
GRAPHQL_URL = "https://id.jobstreet.com/graphql"
JOB_URL = "https://id.jobstreet.com/job/{job_id}"

JOB_DETAILS_QUERY = """
query jobDetails($jobId: ID!) {
  jobDetails(id: $jobId) {
    job {
      title
      content(platform: WEB)
      workTypes { label }
    }
  }
}
""".strip()


def search(query: str, location_conf: dict, limit: int = 15) -> list[dict]:
    """Cari lowongan di JobStreet untuk satu kata kunci dan satu wilayah."""
    params = {
        "siteKey": "ID-Main",
        "sourcesystem": "houston",
        "locale": "id-ID",
        "keywords": query,
        "where": location_conf["jobstreet"],
        "page": 1,
        "pageSize": min(max(limit, 10), 30),
    }

    try:
        data = base.get_json(f"{SEARCH_URL}?{urlencode(params)}")
    except Exception as e:
        raise SourceError(f"gagal akses JobStreet: {e}") from e

    results = []
    for item in data.get("data", [])[:limit]:
        locations = [
            loc.get("label", "") for loc in item.get("locations", []) if loc.get("label")
        ]
        arrangements = [
            (w.get("label") or {}).get("text", "")
            for w in (item.get("workArrangements") or {}).get("data", [])
        ]
        work_types = item.get("workTypes") or []
        job_id = str(item.get("id", ""))

        results.append(
            base.make_job(
                title=item.get("title", ""),
                company=item.get("companyName")
                or (item.get("advertiser") or {}).get("description", ""),
                location=", ".join(locations),
                url=JOB_URL.format(job_id=job_id) if job_id else "",
                source=NAME,
                work_mode=base.normalize_work_mode(
                    arrangements[0] if arrangements else ""
                ),
                employment_type=", ".join(work_types),
                salary=item.get("salaryLabel", ""),
                posted=item.get("listingDateDisplay") or item.get("listingDate", ""),
                teaser=(item.get("teaser") or "").strip(),
                external_id=job_id,
            )
        )

    return results


def fetch_description(job: dict) -> str:
    """Ambil job description lengkap lewat GraphQL JobStreet."""
    job_id = job.get("external_id")
    if not job_id:
        return ""

    import requests

    payload = {
        "operationName": "jobDetails",
        "variables": {"jobId": str(job_id)},
        "query": JOB_DETAILS_QUERY,
    }
    headers = {
        **base.HEADERS,
        "Content-Type": "application/json",
        "Referer": "https://id.jobstreet.com/",
    }

    resp = requests.post(GRAPHQL_URL, json=payload, headers=headers, timeout=25)
    resp.raise_for_status()
    body = resp.json()

    if body.get("errors"):
        raise SourceError(body["errors"][0].get("message", "GraphQL error"))

    detail = ((body.get("data") or {}).get("jobDetails") or {}).get("job") or {}
    return base.clean_html(detail.get("content", ""))
