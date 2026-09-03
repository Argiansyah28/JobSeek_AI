"""
AI Agent — memakai Google Gemini API (gratis).

Tugas:
  1. Ekstrak kata kunci penting dari job description
  2. Sesuaikan CV agar cocok dengan lowongan
  3. Buat draf email lamaran (Bahasa Indonesia atau Inggris)
"""

import time

from google import genai
from google.genai import types

from config import (
    GEMINI_API_KEY,
    GEMINI_MODELS,
    GEMINI_TIMEOUT,
    GEMINI_TOTAL_BUDGET,
    MY_NAME,
    MY_EMAIL,
    MY_PHONE,
)

_client = None
_active_model = None

# Gemini menolak deadline yang terlalu pendek, jadi jangan meminta di bawah ini.
MIN_DEADLINE = 30


def _get_client():
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY belum diisi. Isi di config.py atau set "
                "environment variable GEMINI_API_KEY."
            )
        _client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(
                    attempts=2,
                    # 503/429 lumrah di kuota gratis dan biasanya sesaat saja.
                    # 504 sengaja TIDAK diikutkan: itu artinya deadline kita
                    # sendiri sudah lewat, mengulanginya cuma melipatgandakan
                    # waktu tunggu.
                    http_status_codes=[429, 500, 502, 503],
                ),
            ),
        )
    return _client


def active_model() -> str | None:
    """Model yang terakhir berhasil dipakai (untuk ditampilkan di dashboard)."""
    return _active_model


def _ask(prompt: str) -> str:
    """
    Kirim prompt ke Gemini.

    Percobaan ulang untuk error sesaat (503/429) sudah ditangani SDK lewat
    retry_options, jadi di sini tugasnya hanya berpindah model kalau satu
    model bermasalah — misalnya dipensiunkan Google.

    Seluruh proses dibatasi GEMINI_TOTAL_BUDGET supaya saat server Gemini
    tidak responsif, dashboard cepat memberi pesan gagal alih-alih
    menggantung berlama-lama menunggu tiap model.
    """
    global _active_model
    client = _get_client()

    # Model yang sudah terbukti jalan dicoba duluan.
    candidates = list(GEMINI_MODELS)
    if _active_model and _active_model in candidates:
        candidates.remove(_active_model)
        candidates.insert(0, _active_model)

    deadline = time.monotonic() + GEMINI_TOTAL_BUDGET
    last_error = None

    for model in candidates:
        remaining = deadline - time.monotonic()
        # Gemini menolak deadline yang terlalu pendek, jadi kalau sisa waktu
        # sudah di bawah batas minimum, berhenti saja.
        if remaining < MIN_DEADLINE:
            last_error = last_error or TimeoutError("waktu habis sebelum sempat mencoba")
            break

        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                # Deadline tiap panggilan mengikuti sisa budget, supaya
                # percobaan model terakhir tidak melewati batas total.
                config=types.GenerateContentConfig(
                    http_options=types.HttpOptions(
                        timeout=int(min(GEMINI_TIMEOUT, remaining) * 1000)
                    )
                ),
            )
            text = (response.text or "").strip()
            if text:
                _active_model = model
                return text
            last_error = RuntimeError(f"{model} membalas kosong")
        except Exception as e:  # noqa: BLE001 - API pihak ketiga
            last_error = e

    raise RuntimeError(
        f"Gemini tidak bisa dihubungi. Terakhir: {last_error}. "
        "Biasanya server sedang sibuk — coba lagi beberapa menit lagi."
    )


def extract_keywords(job_description: str) -> str:
    """Ekstrak kata kunci penting dari job description."""
    return _ask(f"""Analisis job description berikut, lalu tuliskan dalam Bahasa Indonesia:

1. Hard skill yang diminta (bahasa pemrograman, framework, tools)
2. Soft skill yang diminta
3. Tanggung jawab utama
4. Kata kunci penting yang sebaiknya muncul di CV
5. Level pengalaman yang dicari

Job Description:
{job_description[:4000]}

Jawab ringkas dalam bentuk poin-poin. Spesifik, jangan mengarang.""")


def analyze_fit(cv_text: str, job_title: str, job_description: str) -> str:
    """Nilai seberapa cocok CV dengan lowongan, dan apa yang masih kurang."""
    return _ask(f"""Kamu konsultan karier. Bandingkan CV berikut dengan sebuah lowongan.

Tulis dalam Bahasa Indonesia, ringkas:
1. SKOR KECOCOKAN: angka 0-100 beserta alasan singkat (1-2 kalimat)
2. YANG SUDAH COCOK: skill/pengalaman di CV yang relevan
3. YANG MASIH KURANG: syarat lowongan yang belum ada di CV
4. SARAN: langkah konkret agar peluang diterima naik

Jujur dan realistis. Jangan mengarang pengalaman yang tidak ada di CV.

CV saya:
{cv_text}

Posisi yang dilamar: {job_title}

Job Description:
{job_description[:4000]}""")


def tailor_cv(cv_text: str, job_title: str, job_description: str) -> str:
    """Sesuaikan CV agar cocok dengan lowongan tertentu."""
    return _ask(f"""Kamu konsultan CV profesional.
Berdasarkan CV saya dan lowongan target, tulis ulang bagian "ABOUT ME" dan
susun ulang / rumuskan ulang poin di bagian "EXPERIENCES", "PROJECT EXPERIENCE",
dan "SKILLS" agar lebih cocok dengan lowongan tersebut.

ATURAN:
- JANGAN mengarang pengalaman atau skill yang tidak saya miliki.
- JANGAN mengubah data pribadi, pendidikan, atau kontak.
- TONJOLKAN skill dan pengalaman yang relevan dengan lowongan.
- PAKAI kata kunci dari job description secara natural.
- Ringkas, profesional, dan siap dipakai melamar.
- Keluarkan CV lengkap hasil penyesuaian dalam format teks biasa.

CV saya saat ini:
{cv_text}

Posisi target: {job_title}

Job Description:
{job_description[:4000]}

Keluarkan CV hasil penyesuaian sekarang:""")


def draft_email(
    cv_text: str,
    job_title: str,
    company: str,
    job_description: str,
    language: str = "id",
) -> str:
    """Buat draf email lamaran kerja."""
    lang_rule = (
        "Tulis dalam Bahasa Indonesia yang profesional."
        if language == "id"
        else "Write the email in professional English."
    )

    return _ask(f"""Tulis draf email lamaran kerja. {lang_rule}

ATURAN:
- Isi email maksimal 200 kata.
- Sebutkan secara spesifik kenapa saya cocok, berdasarkan CV dan lowongan.
- Profesional tapi tidak kaku — tunjukkan minat yang tulus.
- Sertakan baris "Subject:" di paling atas.
- Tutup dengan info kontak saya.
- Jangan mengarang pengalaman yang tidak ada di CV.

Nama saya: {MY_NAME}
Email saya: {MY_EMAIL}
HP saya: {MY_PHONE}

Ringkasan CV saya:
{cv_text[:2000]}

Melamar untuk: {job_title} di {company}

Poin penting dari job description:
{job_description[:2000]}

Tulis emailnya sekarang:""")
