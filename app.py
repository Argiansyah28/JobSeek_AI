"""
Web dashboard JobSeek AI.

Jalankan:  python app.py
Lalu buka: http://127.0.0.1:5000

Pencarian dan pemrosesan AI dijalankan di thread terpisah supaya halaman
tidak membeku; frontend memantau progresnya lewat polling /api/task/<id>.
"""

import os
import re
import sys
import threading
import traceback
import uuid
import webbrowser
from datetime import datetime

from flask import Flask, jsonify, render_template, request, send_from_directory

import agent
import scraper
from config import (
    CV_FILE,
    ENRICH_LINKEDIN,
    GEMINI_API_KEY,
    INTERNSHIP_QUERIES,
    JOB_QUERIES,
    LIMIT_PER_QUERY,
    LOCATIONS,
    LOCATION_ORDER,
    MY_EMAIL,
    MY_NAME,
    OUTPUT_DIR,
    SOURCES,
)
from sources import REGISTRY

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(BASE_DIR, OUTPUT_DIR)

app = Flask(__name__)

# Penyimpanan tugas latar belakang. Dashboard ini dipakai satu orang
# di localhost, jadi dict in-memory sudah cukup.
_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()

# Hasil pencarian terakhir, supaya /api/process bisa merujuk lowongan by id.
_last_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


# ============================ Task helper ============================

def _new_task() -> str:
    task_id = uuid.uuid4().hex[:12]
    with _tasks_lock:
        _tasks[task_id] = {
            "status": "running",
            "progress": 0,
            "log": [],
            "result": None,
            "error": None,
        }
    return task_id


def _update(task_id: str, *, message=None, progress=None, status=None,
            result=None, error=None):
    with _tasks_lock:
        task = _tasks.get(task_id)
        if task is None:
            return
        if message:
            task["log"].append(message)
            task["log"] = task["log"][-60:]
        if progress is not None:
            task["progress"] = progress
        if status:
            task["status"] = status
        if result is not None:
            task["result"] = result
        if error is not None:
            task["error"] = error


def _run_bg(task_id: str, fn):
    """Jalankan fn() di thread, tangkap error apa pun jadi status task."""
    def wrapper():
        try:
            result = fn(lambda msg, pct: _update(task_id, message=msg, progress=pct))
            _update(task_id, status="done", progress=100, result=result)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            _update(
                task_id,
                status="error",
                error=f"{type(e).__name__}: {e}",
                message=f"Gagal: {e}",
            )

    threading.Thread(target=wrapper, daemon=True).start()


# ============================ CV ============================

def load_cv() -> str:
    path = os.path.join(BASE_DIR, CV_FILE)
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ============================ Routes: halaman ============================

@app.route("/")
def index():
    return render_template(
        "index.html",
        locations=[
            {"key": k, "label": LOCATIONS[k]["label"]} for k in LOCATION_ORDER
        ],
        sources=[{"key": s, "label": REGISTRY[s].NAME} for s in SOURCES],
        job_queries=JOB_QUERIES,
        internship_queries=INTERNSHIP_QUERIES,
        limit_per_query=LIMIT_PER_QUERY,
        enrich_default=ENRICH_LINKEDIN,
        my_name=MY_NAME,
        my_email=MY_EMAIL,
        cv_loaded=bool(load_cv().strip()),
        api_key_set=bool(GEMINI_API_KEY),
    )


# ============================ Routes: API ============================

@app.route("/api/search", methods=["POST"])
def api_search():
    """Mulai pencarian lowongan di latar belakang."""
    body = request.get_json(force=True) or {}

    mode = body.get("mode", scraper.MODE_JOB)
    if mode not in (scraper.MODE_JOB, scraper.MODE_INTERNSHIP):
        return jsonify({"error": "mode harus 'job' atau 'internship'"}), 400

    location_keys = [k for k in body.get("locations", []) if k in LOCATIONS]
    if not location_keys:
        return jsonify({"error": "Pilih minimal satu wilayah."}), 400

    source_keys = [s for s in body.get("sources", []) if s in REGISTRY]
    if not source_keys:
        return jsonify({"error": "Pilih minimal satu sumber."}), 400

    queries = [q.strip() for q in body.get("queries", []) if q.strip()]
    if not queries:
        queries = scraper.default_queries(mode)

    limit = max(5, min(int(body.get("limit") or LIMIT_PER_QUERY), 30))
    enrich = bool(body.get("enrich", ENRICH_LINKEDIN))
    cv_text = load_cv()
    task_id = _new_task()

    def work(progress):
        result = scraper.search_jobs(
            mode=mode,
            queries=queries,
            location_keys=location_keys,
            source_keys=source_keys,
            limit_per_query=limit,
            cv_text=cv_text,
            enrich=enrich,
            progress=progress,
        )

        # Beri id stabil supaya frontend bisa minta proses lowongan tertentu.
        with _jobs_lock:
            _last_jobs.clear()
            for i, job in enumerate(result["jobs"]):
                job["id"] = f"{job['source'].lower()}-{job.get('external_id') or i}"
                _last_jobs[job["id"]] = job

        return result

    _run_bg(task_id, work)
    return jsonify({"task_id": task_id})


@app.route("/api/process", methods=["POST"])
def api_process():
    """
    Proses satu lowongan dengan AI:
    ambil JD lengkap -> analisis kecocokan -> kata kunci -> CV disesuaikan -> draf email.
    """
    body = request.get_json(force=True) or {}
    job_id = body.get("job_id")

    with _jobs_lock:
        job = _last_jobs.get(job_id)

    if job is None:
        return jsonify({"error": "Lowongan tidak ditemukan. Coba cari ulang."}), 404

    cv_text = load_cv()
    if not cv_text.strip():
        return jsonify({"error": f"File CV '{CV_FILE}' kosong atau tidak ada."}), 400

    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY belum diisi di config.py."}), 400

    language = body.get("language", "id")
    task_id = _new_task()

    def work(progress):
        title = job["title"]
        company = job["company"]

        progress("Mengambil job description lengkap...", 5)
        description = job.get("description") or ""
        if not description:
            try:
                description = scraper.fetch_description(job)
            except Exception as e:  # noqa: BLE001
                progress(f"JD lengkap gagal diambil ({e}), pakai ringkasan.", 10)

        if not description.strip():
            description = job.get("teaser") or ""
        if not description.strip():
            raise RuntimeError(
                "Job description tidak bisa diambil dari sumbernya. "
                "Buka link lowongan, copy JD-nya, lalu pakai menu 'Input Manual'."
            )

        job["description"] = description
        progress(f"JD siap ({len(description)} karakter).", 20)

        progress("Menganalisis kecocokan CV dengan lowongan...", 30)
        fit = agent.analyze_fit(cv_text, title, description)

        progress("Mengekstrak kata kunci dari job description...", 50)
        keywords = agent.extract_keywords(description)

        progress("Menyesuaikan CV dengan lowongan...", 70)
        tailored = agent.tailor_cv(cv_text, title, description)

        progress("Menyusun draf email lamaran...", 88)
        email = agent.draft_email(cv_text, title, company, description, language)

        progress("Menyimpan hasil ke folder output...", 96)
        files = _save_outputs(company, title, {
            "analisis_kecocokan": fit,
            "kata_kunci": keywords,
            "cv_disesuaikan": tailored,
            "draf_email": email,
        })

        return {
            "job": {
                "title": title,
                "company": company,
                "location": job.get("location"),
                "work_mode": job.get("work_mode"),
                "url": job.get("url"),
                "source": job.get("source"),
            },
            "fit": fit,
            "keywords": keywords,
            "tailored_cv": tailored,
            "email": email,
            "description": description,
            "files": files,
            "model": agent.active_model(),
        }

    _run_bg(task_id, work)
    return jsonify({"task_id": task_id})


@app.route("/api/manual", methods=["POST"])
def api_manual():
    """Daftarkan lowongan hasil input manual (paste JD atau URL) supaya bisa diproses."""
    body = request.get_json(force=True) or {}

    title = (body.get("title") or "").strip() or "Posisi Tidak Disebutkan"
    company = (body.get("company") or "").strip() or "Perusahaan Tidak Disebutkan"
    description = (body.get("description") or "").strip()
    url = (body.get("url") or "").strip()

    if not description:
        return jsonify({"error": "Job description tidak boleh kosong."}), 400

    from sources import base as sbase

    job = sbase.make_job(
        title=title,
        company=company,
        location=(body.get("location") or "").strip(),
        url=url,
        source="Manual",
        work_mode=sbase.detect_work_mode(title, description),
    )
    job["description"] = description
    job["match_score"] = 0
    job["id"] = f"manual-{uuid.uuid4().hex[:8]}"

    with _jobs_lock:
        _last_jobs[job["id"]] = job

    return jsonify({"job": job})


@app.route("/api/task/<task_id>")
def api_task(task_id):
    with _tasks_lock:
        task = _tasks.get(task_id)
        if task is None:
            return jsonify({"error": "task tidak ditemukan"}), 404
        return jsonify(dict(task))


@app.route("/api/cv", methods=["GET", "POST"])
def api_cv():
    """Lihat dan simpan isi CV langsung dari dashboard."""
    path = os.path.join(BASE_DIR, CV_FILE)

    if request.method == "GET":
        return jsonify({"content": load_cv(), "filename": CV_FILE})

    content = (request.get_json(force=True) or {}).get("content", "")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return jsonify({"ok": True, "chars": len(content)})


@app.route("/output/<path:filename>")
def api_output(filename):
    return send_from_directory(OUTPUT_PATH, filename, as_attachment=True)


# ============================ Output ============================

def _save_outputs(company: str, title: str, sections: dict[str, str]) -> list[dict]:
    """Simpan tiap bagian hasil AI ke file terpisah di folder output/."""
    os.makedirs(OUTPUT_PATH, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = _slugify(f"{company}_{title}")[:50]

    saved = []
    for name, content in sections.items():
        filename = f"{slug}__{name}__{stamp}.txt"
        with open(os.path.join(OUTPUT_PATH, filename), "w", encoding="utf-8") as f:
            f.write(content)
        saved.append({"label": name.replace("_", " ").title(), "file": filename})

    return saved


def _slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text or "", flags=re.UNICODE)
    return re.sub(r"[\s]+", "_", text).strip("_") or "lowongan"


# ============================ Entry point ============================

def main():
    os.makedirs(OUTPUT_PATH, exist_ok=True)

    if not load_cv().strip():
        print(f"⚠  File CV '{CV_FILE}' kosong / tidak ada.")
        print("   Kamu tetap bisa mengisinya lewat tab 'CV Saya' di dashboard.\n")

    if not GEMINI_API_KEY:
        print("⚠  GEMINI_API_KEY belum diisi — fitur AI tidak akan jalan.")
        print("   Ambil key gratis di https://aistudio.google.com/apikey\n")

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    url = f"http://{host}:{port}"

    print("╔══════════════════════════════════╗")
    print("║   JobSeek AI — Web Dashboard     ║")
    print("╚══════════════════════════════════╝")
    print(f"\n  Dashboard jalan di: {url}")
    print("  Tekan Ctrl+C untuk berhenti.\n")

    # Buka browser otomatis hanya saat dijalankan di komputer sendiri.
    # Di hosting, HOST diisi 0.0.0.0 dan tidak ada browser untuk dibuka.
    # Syarat kedua mencegah browser terbuka dua kali saat Flask reloader aktif.
    is_local = host in ("127.0.0.1", "localhost")
    if is_local and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    sys.exit(main())
