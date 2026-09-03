"""
Orkestrator pencarian lowongan.

Alur:
  1. Untuk tiap kata kunci x wilayah x sumber -> ambil daftar lowongan.
  2. Saring supaya hanya lowongan di Kota Tangerang / Tangerang Selatan / Jakarta.
  3. Saring sesuai mode: "job" (kerja tetap) atau "internship" (magang).
  4. Buang duplikat antar sumber, hitung skor kecocokan dengan CV, urutkan.

Job description lengkap TIDAK diambil di tahap ini (lambat sekali kalau
puluhan lowongan). Diambil belakangan lewat fetch_description() saat satu
lowongan benar-benar diproses AI.
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (
    ENRICH_LIMIT,
    ENRICH_LINKEDIN,
    GENERIC_TERMS,
    JOB_QUERIES,
    INTERNSHIP_QUERIES,
    LIMIT_PER_QUERY,
    LOCATIONS,
    LOCATION_ORDER,
    SOURCES,
)
from sources import REGISTRY
from sources import base as sbase
from sources.base import SourceError

MODE_JOB = "job"
MODE_INTERNSHIP = "internship"


def default_queries(mode: str) -> list[str]:
    return list(INTERNSHIP_QUERIES if mode == MODE_INTERNSHIP else JOB_QUERIES)


def search_jobs(
    mode: str = MODE_JOB,
    queries: list[str] | None = None,
    location_keys: list[str] | None = None,
    source_keys: list[str] | None = None,
    limit_per_query: int = LIMIT_PER_QUERY,
    cv_text: str = "",
    enrich: bool = ENRICH_LINKEDIN,
    progress=None,
) -> dict:
    """
    Cari lowongan dari semua sumber.

    progress: callback opsional progress(pesan: str, persen: int) untuk dashboard.
    Return: {"jobs": [...], "errors": [...], "stats": {...}}
    """
    queries = queries or default_queries(mode)
    location_keys = location_keys or list(LOCATION_ORDER)
    source_keys = source_keys or list(SOURCES)

    def report(msg, pct):
        if progress:
            progress(msg, pct)

    tasks = [
        (src, query, loc_key)
        for src in source_keys
        for query in queries
        for loc_key in location_keys
        # Glints tidak difilter per wilayah di sisi server, jadi cukup sekali
        # per kata kunci — hasilnya disaring lokasi belakangan.
        if not (src == "glints" and loc_key != location_keys[0])
    ]

    raw_jobs: list[dict] = []
    errors: list[str] = []
    done = 0
    total = max(len(tasks), 1)

    report("Mulai mencari...", 0)

    # Paralel tapi hemat: 4 request bersamaan supaya tidak dianggap abuse.
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(_run_one, src, query, loc_key, limit_per_query, mode):
                (src, query, loc_key)
            for src, query, loc_key in tasks
        }

        for future in as_completed(futures):
            src, query, loc_key = futures[future]
            done += 1
            pct = int(done / total * 80)

            try:
                found = future.result()
                raw_jobs.extend(found)
                label = LOCATIONS[loc_key]["label"]
                report(
                    f"{REGISTRY[src].NAME} · \"{query}\" · {label} → {len(found)} hasil",
                    pct,
                )
            except SourceError as e:
                msg = f"{REGISTRY[src].NAME} gagal untuk \"{query}\": {e}"
                if msg not in errors:
                    errors.append(msg)
                report(msg, pct)
            except Exception as e:  # noqa: BLE001 - sumber pihak ketiga, apa saja bisa terjadi
                msg = f"{REGISTRY[src].NAME} error untuk \"{query}\": {type(e).__name__}: {e}"
                if msg not in errors:
                    errors.append(msg)
                report(msg, pct)

    report(f"Menyaring {len(raw_jobs)} lowongan mentah...", 82)

    in_area = _filter_by_location(raw_jobs, location_keys)
    unique = _deduplicate(in_area)
    on_mode = _filter_by_mode(unique, mode)

    # Pengayaan dijalankan paling akhir supaya hanya lowongan yang benar-benar
    # ditampilkan yang halaman detailnya diunduh.
    if enrich:
        _enrich_linkedin(on_mode, report)

    report("Menghitung kecocokan dengan CV...", 96)
    for job in on_mode:
        job["match_score"] = _match_score(job, cv_text)

    on_mode.sort(key=lambda j: (-j["match_score"], j["company"].lower()))

    report(f"Selesai — {len(on_mode)} lowongan cocok.", 100)

    return {
        "jobs": on_mode,
        "errors": errors,
        "stats": {
            "raw": len(raw_jobs),
            "in_area": len(in_area),
            "unique": len(unique),
            "final": len(on_mode),
        },
    }


def _enrich_linkedin(jobs: list[dict], report) -> None:
    """
    Ambil halaman detail LinkedIn untuk lowongan yang mode kerjanya belum jelas.

    Mode kerja dideteksi dari isi job description, dan deskripsinya disimpan
    di record lowongan supaya proses AI nanti tidak perlu mengunduh ulang.

    Field "Jenis pekerjaan" dari LinkedIn sengaja TIDAK dipakai: versi
    Indonesianya sering salah label (banyak lowongan magang ditulis
    "Sukarelawan"), jadi pemisahan job vs magang tetap mengandalkan judul.
    """
    targets = [
        j for j in jobs
        if j["source"] == REGISTRY["linkedin"].NAME
        and j["work_mode"] == sbase.UNKNOWN
        and j.get("external_id")
    ][:ENRICH_LIMIT]

    if not targets:
        return

    report(f"Mengambil detail {len(targets)} lowongan LinkedIn...", 86)
    done = 0

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(REGISTRY["linkedin"].fetch_description, job): job
            for job in targets
        }

        for future in as_completed(futures):
            job = futures[future]
            done += 1

            try:
                description = future.result()
            except Exception:  # noqa: BLE001 - detail gagal bukan alasan membatalkan pencarian
                continue

            if not description:
                continue

            job["description"] = description
            job["work_mode"] = sbase.detect_work_mode(
                job["title"], job["location"], description
            )

            if done % 10 == 0:
                report(f"Detail LinkedIn: {done}/{len(targets)}", 86 + int(done / len(targets) * 8))


def _run_one(src: str, query: str, loc_key: str, limit: int, mode: str) -> list[dict]:
    """Jalankan satu kombinasi sumber x kata kunci x wilayah."""
    module = REGISTRY[src]
    loc_conf = LOCATIONS[loc_key]

    if src == "glints":
        # Glints punya filter tipe pekerjaan yang akurat, dipakai langsung.
        found = module.search(
            query, loc_conf, limit=limit, internship=(mode == MODE_INTERNSHIP)
        )
    else:
        found = module.search(query, loc_conf, limit=limit)

    time.sleep(0.3)
    return found


def _filter_by_location(jobs: list[dict], location_keys: list[str]) -> list[dict]:
    """Hanya simpan lowongan yang lokasinya masuk wilayah yang dipilih."""
    allowed = set(location_keys)
    kept = []

    for job in jobs:
        key, label = sbase.match_location(job.get("location", ""))
        if key and key in allowed:
            job["location_key"] = key
            job["location_label"] = label
            kept.append(job)

    return kept


def _filter_by_mode(jobs: list[dict], mode: str) -> list[dict]:
    """
    Pisahkan lowongan kerja tetap dari magang.

    Sinyal terkuat: employment_type dari sumber ("Magang" / "Internship").
    Kalau sumber tidak memberi tipe (LinkedIn), jatuh ke kata kunci di judul.
    """
    kept = []

    for job in jobs:
        etype = (job.get("employment_type") or "").lower()
        title = job.get("title", "")

        if "magang" in etype or "intern" in etype:
            is_intern = True
        elif etype:
            # Sumber menyebut tipe lain (Full time / Kontrak) — tapi judul
            # masih bisa bilang "Internship Program" (JobStreet sering begitu).
            is_intern = sbase.looks_like_internship(title)
        else:
            is_intern = sbase.looks_like_internship(title)

        if mode == MODE_INTERNSHIP and is_intern:
            kept.append(job)
        elif mode == MODE_JOB and not is_intern:
            kept.append(job)

    return kept


def _deduplicate(jobs: list[dict]) -> list[dict]:
    """
    Buang lowongan kembar. Satu lowongan sering muncul di dua situs sekaligus,
    jadi kunci dedup-nya judul + perusahaan yang sudah dinormalkan.
    """
    seen: dict[str, dict] = {}

    for job in jobs:
        key = f"{_normalize(job['title'])}|{_normalize(job['company'])}"
        existing = seen.get(key)

        if existing is None:
            job["also_on"] = []
            seen[key] = job
            continue

        # Sudah ada. Catat sumber lain, dan pertahankan record paling informatif.
        if job["source"] not in existing["also_on"] and job["source"] != existing["source"]:
            existing["also_on"].append(job["source"])

        if existing["work_mode"] == sbase.UNKNOWN and job["work_mode"] != sbase.UNKNOWN:
            existing["work_mode"] = job["work_mode"]
        if not existing["salary"] and job["salary"]:
            existing["salary"] = job["salary"]
        if not existing["employment_type"] and job["employment_type"]:
            existing["employment_type"] = job["employment_type"]

    return list(seen.values())


def _normalize(text: str) -> str:
    """Turunkan judul/perusahaan ke bentuk baku untuk dibandingkan."""
    text = (text or "").lower()
    text = re.sub(r"\b(pt|cv|tbk|persero|inc|ltd|llc|group)\b", " ", text)
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _match_score(job: dict, cv_text: str) -> int:
    """
    Skor kecocokan kasar 0-100 antara lowongan dan CV, tanpa panggilan AI.
    Dipakai untuk mengurutkan daftar, bukan sebagai penilaian mutlak —
    penilaian sungguhan dikerjakan Gemini lewat agent.analyze_fit().

    Kata terlalu umum ("developer", "engineer", "jakarta") dibuang lebih dulu,
    supaya yang dinilai benar-benar istilah teknis seperti react / golang / ai.
    """
    if not cv_text:
        return 0

    cv_tokens = _tokens(cv_text) - GENERIC_TERMS
    job_tokens = _tokens(" ".join([
        job.get("title", ""),
        job.get("teaser", ""),
        job.get("description", "")[:1500],
        " ".join(job.get("skills") or []),
    ]))
    specific = job_tokens - GENERIC_TERMS

    # Bobot 1: kecocokan peran (frontend / backend / ai / dst) dari judul.
    title_tokens = _tokens(job.get("title", ""))
    role_hit = bool(title_tokens & cv_tokens)
    role_part = 40 if role_hit else 10

    # Bobot 2: berapa banyak istilah teknis lowongan yang ada di CV.
    if not specific:
        # Judul polos tanpa istilah teknis — tidak ada bukti tambahan.
        return role_part + 15

    matched = len(specific & cv_tokens)
    coverage = matched / len(specific)

    # Lowongan dengan sedikit sekali kata (judul saja) tidak boleh langsung
    # dapat nilai penuh, jadi coverage dibatasi oleh jumlah kecocokan absolut.
    confidence = min(1.0, matched / 6)
    skill_part = 60 * coverage * (0.45 + 0.55 * confidence)

    return max(0, min(100, round(role_part + skill_part)))


def _tokens(text: str) -> set[str]:
    """Pecah teks jadi himpunan kata untuk dibandingkan."""
    return set(re.findall(r"[a-z0-9+#]{2,}", (text or "").lower()))


def fetch_description(job: dict) -> str:
    """
    Ambil job description lengkap untuk satu lowongan, dari sumber aslinya.
    Dipanggil saat lowongan mau diproses AI.
    """
    src_name = (job.get("source") or "").lower()
    module = REGISTRY.get(src_name)

    if module is None:
        raise SourceError(f"sumber tidak dikenal: {job.get('source')}")

    return module.fetch_description(job)
