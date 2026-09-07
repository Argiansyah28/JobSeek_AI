/* JobSeek AI — logika dashboard */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

let currentMode = null;
let allJobs = [];

/* ============================ ikon ============================ */

const icon = (paths, extra = "") =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
        stroke-linecap="round" stroke-linejoin="round" ${extra}>${paths}</svg>`;

const ICONS = {
  home: icon(`<path d="M3 10.5 12 3.5l9 7"/><path d="M5.5 9.5V20h13V9.5"/>`),
  building: icon(`<rect x="4.5" y="3" width="15" height="18" rx="2"/>
                  <path d="M9 7.5h1.5M13.5 7.5H15M9 12h1.5M13.5 12H15M10.5 21v-4h3v4"/>`),
  swap: icon(`<path d="M4 8.5h13a3.5 3.5 0 0 1 0 7H7"/><path d="m9.5 4.5-4 4 4 4"/>`),
  question: icon(`<circle cx="12" cy="12" r="8.5"/>
                  <path d="M9.6 9.5a2.5 2.5 0 1 1 2.7 3.3v1.3"/><path d="M12.3 17.2h.01"/>`),
  pin: icon(`<path d="M12 21s7-5.4 7-11a7 7 0 1 0-14 0c0 5.6 7 11 7 11z"/>
             <circle cx="12" cy="10" r="2.6"/>`),
  wallet: icon(`<rect x="3" y="6" width="18" height="13" rx="2.2"/>
                <path d="M3 10h18M16.5 14.5h.01"/>`),
  clock: icon(`<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 1.8"/>`),
  external: icon(`<path d="M14 4h6v6"/><path d="m20 4-8.5 8.5"/>
                  <path d="M18 14.5V19a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 4 19V8a1.5 1.5 0 0 1 1.5-1.5H10"/>`),
  spark: icon(`<path d="M12 3.5 13.9 9l5.6 2-5.6 2-1.9 5.5L10.1 13l-5.6-2 5.6-2z"/>`),
  compass: icon(`<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5z"/>`),
};

const WORK_MODE = {
  "WFH":              { cls: "badge-wfh",     icon: ICONS.home,     text: "WFH / Remote" },
  "Hybrid":           { cls: "badge-hybrid",  icon: ICONS.swap,     text: "Hybrid" },
  "WFO":              { cls: "badge-wfo",     icon: ICONS.building, text: "WFO / On-site" },
  "Tidak disebutkan": { cls: "badge-unknown", icon: ICONS.question, text: "Mode kerja tidak disebutkan" },
};

/* ============================ kata penyemangat ============================ */

/* Tiap motto ditulis per baris supaya pemenggalannya tetap sama di layar
   mana pun — bukan diserahkan ke pembungkusan teks otomatis. */
const MOTTOS = [
  ["YOU CAN", "DO IT"],
  ["ONE DAY", "OR DAY ONE"],
];

const WORKING_NOTES = [
  "Sedang membaca lowongan ini baik-baik...",
  "Menyusun kalimat yang pas untukmu...",
  "Sebentar ya, biar hasilnya rapi...",
  "Mencocokkan pengalamanmu dengan yang mereka cari...",
];

function pick(list) {
  return list[Math.floor(Math.random() * list.length)];
}

/** Ganti kata penyemangat di hero dengan transisi lembut. */
function startMottoRotation() {
  const el = $("#heroMotto");
  if (!el) return;

  let i = 0;
  setInterval(() => {
    el.classList.add("fading");
    setTimeout(() => {
      i = (i + 1) % MOTTOS.length;
      el.innerHTML = MOTTOS[i].map((line) => `<span>${line}</span>`).join("");
      el.classList.remove("fading");
    }, 700);
  }, 6000);
}

startMottoRotation();

/* ============================ util ============================ */

function toast(message, isError = false) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.toggle("err", isError);
  el.classList.remove("hidden");
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.add("hidden"), 3400);
}

async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

/**
 * Pantau tugas latar belakang sampai selesai.
 * onTick(task) dipanggil tiap polling supaya progress bisa digambar.
 */
function pollTask(taskId, onTick) {
  return new Promise((resolve, reject) => {
    const timer = setInterval(async () => {
      try {
        const task = await api(`/api/task/${taskId}`);
        onTick(task);
        if (task.status === "done") {
          clearInterval(timer);
          resolve(task.result);
        } else if (task.status === "error") {
          clearInterval(timer);
          reject(new Error(task.error || "Tugas gagal"));
        }
      } catch (e) {
        clearInterval(timer);
        reject(e);
      }
    }, 700);
  });
}

function renderLog(listEl, lines) {
  listEl.innerHTML = lines
    .map((line) => {
      const bad = /gagal|error|diblokir|tidak bisa/i.test(line);
      return `<li class="${bad ? "err" : ""}">${escapeHtml(line)}</li>`;
    })
    .join("");
  listEl.scrollTop = listEl.scrollHeight;
}

function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

/* ============================ tab utama ============================ */

$$("#mainTabs .tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    $$("#mainTabs .tab").forEach((t) => t.classList.remove("active"));
    $$(".tab-panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    $(`#tab-${tab.dataset.tab}`).classList.add("active");
    if (tab.dataset.tab === "cv") loadCv();
  });
});

/* ============================ langkah 1: pilih mode ============================ */

$$(".mode-card").forEach((card) => {
  card.addEventListener("click", () => {
    currentMode = card.dataset.mode;
    $$(".mode-card").forEach((c) => c.classList.remove("selected"));
    card.classList.add("selected");

    $("#modeLabel").textContent =
      currentMode === "internship" ? "— magang" : "— lowongan kerja";
    $("#queriesInput").value = (
      currentMode === "internship"
        ? window.APP_DATA.internshipQueries
        : window.APP_DATA.jobQueries
    ).join("\n");

    $("#stepFilter").classList.remove("hidden");
    $("#stepFilter").scrollIntoView({ behavior: "smooth", block: "nearest" });
  });
});

$("#backToMode").addEventListener("click", () => {
  $("#stepFilter").classList.add("hidden");
  $$(".mode-card").forEach((c) => c.classList.remove("selected"));
  currentMode = null;
  $("#stepMode").scrollIntoView({ behavior: "smooth", block: "nearest" });
});

/* ============================ pencarian ============================ */

$("#searchBtn").addEventListener("click", async () => {
  if (!currentMode) return toast("Pilih dulu jenis pencarian.", true);

  const locations = $$("#locationChecks input:checked").map((i) => i.value);
  const sources = $$("#sourceChecks input:checked").map((i) => i.value);
  if (!locations.length) return toast("Pilih minimal satu wilayah.", true);
  if (!sources.length) return toast("Pilih minimal satu sumber.", true);

  const queries = $("#queriesInput").value.split("\n").map((q) => q.trim()).filter(Boolean);

  const btn = $("#searchBtn");
  btn.disabled = true;
  const originalLabel = btn.innerHTML;
  btn.textContent = "Mencari...";

  $("#searchProgress").classList.remove("hidden");
  $("#resultsBox").classList.add("hidden");
  $("#progressBar").style.width = "0%";
  $("#progressPct").textContent = "0%";
  $("#progressLog").innerHTML = "";
  $("#progressTitle").textContent =
    currentMode === "internship" ? "Mencari lowongan magang..." : "Mencari lowongan kerja...";

  try {
    const { task_id } = await api("/api/search", {
      method: "POST",
      body: JSON.stringify({
        mode: currentMode,
        locations,
        sources,
        queries,
        limit: Number($("#limitInput").value) || 15,
        enrich: $("#enrichInput").checked,
      }),
    });

    const result = await pollTask(task_id, (task) => {
      $("#progressBar").style.width = `${task.progress}%`;
      $("#progressPct").textContent = `${task.progress}%`;
      renderLog($("#progressLog"), task.log);
    });

    allJobs = result.jobs;
    renderResults(result);
  } catch (e) {
    toast(e.message, true);
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalLabel;
  }
});

function renderResults(result) {
  const { jobs, stats, errors } = result;

  $("#resultsBox").classList.remove("hidden");
  $("#resultsTitle").textContent =
    currentMode === "internship" ? "Lowongan Magang" : "Lowongan Kerja";

  const stale = (stats.on_mode || 0) - stats.final;
  let statsText =
    `${stats.final} lowongan cocok · dari ${stats.raw} hasil mentah → ` +
    `${stats.in_area} di wilayahmu → ${stats.unique} setelah duplikat dibuang`;
  if (stale > 0) {
    statsText += ` → ${stale} dibuang karena lebih tua dari ${stats.max_age_days} hari`;
  }
  statsText += ". Diurutkan dari yang terbaru.";
  if (errors.length) statsText += ` ${errors.length} sumber bermasalah — lihat log di atas.`;
  $("#resultsStats").textContent = statsText;

  fillFilter("#filterLocation", jobs.map((j) => j.location_label), "Semua wilayah");
  fillFilter("#filterSource", jobs.map((j) => j.source), "Semua sumber");

  drawJobs();
  $("#resultsBox").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function fillFilter(selector, values, allLabel) {
  const el = $(selector);
  const unique = [...new Set(values.filter(Boolean))].sort();
  el.innerHTML =
    `<option value="">${allLabel}</option>` +
    unique.map((v) => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join("");
}

["#filterWorkMode", "#filterLocation", "#filterSource"].forEach((sel) =>
  $(sel).addEventListener("change", drawJobs)
);

function drawJobs() {
  const wm = $("#filterWorkMode").value;
  const loc = $("#filterLocation").value;
  const src = $("#filterSource").value;

  const shown = allJobs.filter(
    (j) =>
      (!wm || j.work_mode === wm) &&
      (!loc || j.location_label === loc) &&
      (!src || j.source === src)
  );

  const grid = $("#jobGrid");

  if (!shown.length) {
    grid.innerHTML = `
      <div class="empty">
        ${ICONS.compass}
        <strong>Belum ada yang cocok dengan filter ini</strong>
        Coba longgarkan filternya, atau ubah kata kunci lalu cari lagi.
      </div>`;
    return;
  }

  grid.innerHTML = shown.map(jobCard).join("");

  // Kartu muncul bertahap supaya tidak menyerbu sekaligus.
  grid.querySelectorAll(".job-card").forEach((card, i) => {
    card.style.animationDelay = `${Math.min(i * 45, 500)}ms`;
  });

  grid.querySelectorAll("[data-process]").forEach((btn) =>
    btn.addEventListener("click", () => processJob(btn.dataset.process))
  );
}

/** Cincin kecil penunjuk skor kecocokan. */
function scoreRing(score) {
  const r = 19;
  const circumference = 2 * Math.PI * r;
  const offset = circumference * (1 - Math.max(0, Math.min(100, score)) / 100);

  return `
    <div class="score-ring" title="Perkiraan kecocokan dengan CV: ${score}%">
      <svg width="46" height="46" viewBox="0 0 46 46">
        <circle class="track" cx="23" cy="23" r="${r}" fill="none" stroke-width="3"/>
        <circle class="fill" cx="23" cy="23" r="${r}" fill="none" stroke-width="3"
                stroke-linecap="round"
                stroke-dasharray="${circumference.toFixed(1)}"
                stroke-dashoffset="${offset.toFixed(1)}"/>
      </svg>
      <b>${score}</b>
    </div>`;
}

function jobCard(job) {
  const mode = WORK_MODE[job.work_mode] || WORK_MODE["Tidak disebutkan"];

  const alsoOn = (job.also_on || []).length
    ? `<span class="badge badge-src">juga di ${escapeHtml(job.also_on.join(", "))}</span>`
    : "";

  const meta = [
    job.location ? `<span>${ICONS.pin}${escapeHtml(job.location)}</span>` : "",
    job.salary ? `<span>${ICONS.wallet}${escapeHtml(job.salary)}</span>` : "",
    job.posted ? `<span>${ICONS.clock}${escapeHtml(job.posted)}</span>` : "",
  ].join("");

  return `
  <article class="job-card">
    <div class="job-head">
      <div>
        <h3>${escapeHtml(job.title)}</h3>
        <div class="job-company">${escapeHtml(job.company)}</div>
      </div>
      ${scoreRing(job.match_score)}
    </div>

    <div class="badges">
      <span class="badge ${mode.cls}">${mode.icon}${mode.text}</span>
      <span class="badge badge-plain">${escapeHtml(job.location_label || "-")}</span>
      <span class="badge badge-src">${escapeHtml(job.source)}</span>
      ${alsoOn}
      ${job.employment_type ? `<span class="badge badge-plain">${escapeHtml(job.employment_type)}</span>` : ""}
    </div>

    <div class="job-meta">${meta}</div>

    <div class="job-actions">
      <button class="btn btn-primary btn-sm" data-process="${escapeHtml(job.id)}">
        ${ICONS.spark} Proses dengan AI
      </button>
      ${job.url
        ? `<a class="btn btn-sm" href="${escapeHtml(job.url)}" target="_blank" rel="noopener">
             ${ICONS.external} Buka
           </a>`
        : ""}
    </div>
  </article>`;
}

/* ============================ proses AI ============================ */

async function processJob(jobId) {
  const job = allJobs.find((j) => j.id === jobId);
  openModal(
    job ? job.title : "Memproses lowongan",
    job ? `${job.company} · ${job.location_label || job.location || ""}` : ""
  );
  await runAi({ job_id: jobId, language: "id" });
}

async function runAi(payload) {
  $("#modalProgress").classList.remove("hidden");
  $("#modalResult").classList.add("hidden");
  $("#aiBar").style.width = "0%";
  $("#aiLog").innerHTML = "";
  $("#workingNote").textContent = pick(WORKING_NOTES);

  try {
    const { task_id } = await api("/api/process", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    const result = await pollTask(task_id, (task) => {
      $("#aiBar").style.width = `${task.progress}%`;
      renderLog($("#aiLog"), task.log);
    });

    showAiResult(result);
  } catch (e) {
    renderLog($("#aiLog"), [`Gagal: ${e.message}`]);
    $("#workingNote").textContent = "Tidak apa-apa, coba lagi sebentar lagi.";
    toast(e.message, true);
  }
}

function showAiResult(result) {
  $("#modalProgress").classList.add("hidden");
  $("#modalResult").classList.remove("hidden");

  $("#modalTitle").textContent = result.job.title;
  $("#modalSub").textContent = [
    result.job.company,
    result.job.location,
    result.job.work_mode,
    result.model ? `via ${result.model}` : "",
  ].filter(Boolean).join(" · ");

  $("#ai-fit pre").textContent = result.fit;
  $("#ai-keywords pre").textContent = result.keywords;
  $("#ai-cv pre").textContent = result.tailored_cv;
  $("#ai-email pre").textContent = result.email;

  $("#modalFiles").innerHTML =
    "Tersimpan: " +
    result.files
      .map((f) => `<a href="/output/${encodeURIComponent(f.file)}">${escapeHtml(f.label)}</a>`)
      .join(" · ");

  switchAiTab("fit");
}

$$("#aiTabs .tab").forEach((tab) =>
  tab.addEventListener("click", () => switchAiTab(tab.dataset.ai))
);

function switchAiTab(name) {
  $$("#aiTabs .tab").forEach((t) => t.classList.toggle("active", t.dataset.ai === name));
  $$(".ai-panel").forEach((p) => p.classList.toggle("active", p.id === `ai-${name}`));
}

$("#copyBtn").addEventListener("click", async () => {
  const active = $(".ai-panel.active pre");
  if (!active) return;
  try {
    await navigator.clipboard.writeText(active.textContent);
    toast("Tersalin ke clipboard.");
  } catch {
    toast("Browser menolak akses clipboard. Salin manual dari kotak teks.", true);
  }
});

function openModal(title, subtitle) {
  $("#modalTitle").textContent = title;
  $("#modalSub").textContent = subtitle;
  $("#resultModal").classList.remove("hidden");
}

$("#closeModal").addEventListener("click", () => $("#resultModal").classList.add("hidden"));
$("#resultModal").addEventListener("click", (e) => {
  if (e.target.id === "resultModal") $("#resultModal").classList.add("hidden");
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") $("#resultModal").classList.add("hidden");
});

/* ============================ input manual ============================ */

$("#manualBtn").addEventListener("click", async () => {
  const description = $("#manDesc").value.trim();
  if (!description) return toast("Job description tidak boleh kosong.", true);

  const btn = $("#manualBtn");
  btn.disabled = true;

  try {
    const { job } = await api("/api/manual", {
      method: "POST",
      body: JSON.stringify({
        title: $("#manTitle").value,
        company: $("#manCompany").value,
        location: $("#manLocation").value,
        url: $("#manUrl").value,
        description,
      }),
    });

    openModal(job.title, job.company);
    await runAi({ job_id: job.id, language: "id" });
  } catch (e) {
    toast(e.message, true);
  } finally {
    btn.disabled = false;
  }
});

/* ============================ CV ============================ */

async function loadCv() {
  try {
    const { content } = await api("/api/cv");
    $("#cvEditor").value = content;
  } catch (e) {
    toast(e.message, true);
  }
}

$("#saveCvBtn").addEventListener("click", async () => {
  try {
    const { chars } = await api("/api/cv", {
      method: "POST",
      body: JSON.stringify({ content: $("#cvEditor").value }),
    });
    $("#cvStatus").textContent = `Tersimpan — ${chars} karakter.`;
    setTimeout(() => ($("#cvStatus").textContent = ""), 3000);
    toast("CV tersimpan.");
  } catch (e) {
    toast(e.message, true);
  }
});
