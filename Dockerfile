# Dockerfile untuk Hugging Face Spaces (SDK: docker).
# HF menjalankan container sebagai user non-root UID 1000 dan mengarahkan
# trafik ke port 7860 (lihat app_port di frontmatter README.md).

FROM python:3.12-slim

# Buat user non-root sesuai yang diharapkan HF Spaces, supaya app punya izin
# menulis ke folder kerjanya (output/ dan my_cv.txt).
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

# Salin daftar dependensi lebih dulu supaya layer ini di-cache dan tidak
# ikut ter-build ulang setiap kali kode berubah.
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY --chown=user:user . .

EXPOSE 7860

# --workers 1 WAJIB: status pencarian disimpan di memori proses
#               (_tasks / _last_jobs di app.py). Lebih dari satu worker
#               membuat request polling mendarat di proses lain yang kosong.
# --threads 4  : satu proses itu tetap melayani request bersamaan.
# --timeout 300: proses AI bisa berjalan sampai ~200 detik per langkah.
CMD ["gunicorn", "app:app", \
     "--bind", "0.0.0.0:7860", \
     "--workers", "1", \
     "--threads", "4", \
     "--timeout", "300", \
     "--access-logfile", "-"]
