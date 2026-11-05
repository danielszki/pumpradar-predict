/* PumpRadar Predict — consome /api/scan (5 timeframes, polling leve) */
"use strict";

const $ = (s) => document.querySelector(s);
const fmtB = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 });
const fmtU = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 6 });

const TF_ORDER = ["5m", "15m", "1h", "4h", "1d"];
const TF_LABEL = { "5m": "5 min", "15m": "15 min", "1h": "1 hora", "4h": "4 horas", "1d": "1 dia" };
const EX_LABEL = { mexc: "MEXC" };
const SIG_META = {
  rompimento: ["Rompimento", "ssg"],
  volume: ["Volume", "ssv"],
  rs: ["RS vs BTC", "ssr"],
  nova: ["Nova", "ssn"],
};
const STATUS_META = {
  ACAO: ["AÇÃO", "tag up"],
  OBSERVAR: ["OBSERVAR", "tag obs"],
  VIGIA: ["VIGIA", "tag flat"],
};

const state = {
  data: null,
  ex: "mexc",
  active: "1h",
  renderTs: {},
};

async function fetchScan(force, ex) {
  try {
    const r = await fetch("/api/scan?" +
      (ex ? `ex=${ex}` : "") +
      (force ? `${ex ? "&" : ""}force=1` : ""));
    return await r.json();
  } catch (_) { return null; }
}

/* ---------------------------------------------------------------- status */
function updateStatus() {
  const box = $("#scanStatus");
  if (!box) return;
  const dot = $("#statusDot");
  const txt = $("#statusText");
  const cnt = $("#statusCount");
  const d = state.data;

  if (!d) {
    dot.className = "status-dot scanning";
    txt.textContent = "aguardando primeira varredura...";
    cnt.textContent = "";
    return;
  }
  const ready = TF_ORDER.filter(tf => d.tfs[tf] && d.tfs[tf].ts > 0);
  if (d.scanning || ready.length < TF_ORDER.length) {
    dot.className = "status-dot scanning";
    const done = ready.length;
    txt.textContent = `varrendo o mercado... ${done}/5 timeframes prontos`;
    cnt.textContent = "";
    return;
  }
  const next = d.next_in;
  const m = Math.floor(next / 60), s = next % 60;
  dot.className = "status-dot ok";
  txt.textContent = `última varredura há ${ageFmt(d.age)} · próxima em ${m}:${String(s).padStart(2, "0")}`;
  const scanned = ready.map(tf => d.tfs[tf].scanned).reduce((a, b) => a + b, 0);
  cnt.textContent = `${scanned} sinais em ${ready.map(tf => d.tfs[tf].elapsed).reduce((a, b) => a + b, 0)}s`;
  const exl = EX_LABEL[d.ex] || d.ex;
  $("#foot").textContent =
    `PumpRadar Predict · ${exl} · ${d.tfs["1h"].total} perpétuos USDT · 5 timeframes monitorados · atualização automática a cada ${Math.round(d.ttl / 60)} min`;
}

function ageFmt(sec) {
  if (sec < 60) return sec + "s";
  return Math.floor(sec / 60) + "min";
}

/* ---------------------------------------------------------------- render */
function drawView() {
  const d = state.data;
  if (!d) {
    $("#view").innerHTML = `<div class="splash"><div class="spinner"></div><p>Varrendo ~400 perpétuos em 5 timeframes...</p></div>`;
    return;
  }
  const anyRows = TF_ORDER.some(tf => d.tfs[tf] && d.tfs[tf].rows.length);
  if (!anyRows) {
    $("#view").innerHTML =
      `<div class="splash"><div class="spinner"></div><p>Varrendo ~400 perpétuos em 5 timeframes...</p></div>`;
    return;
  }

  const sum = d.summary || {};
  const tf = state.active;
  const t = d.tfs[tf];
  const rows = (t ? t.rows : []).slice(0, 20);
  const ts = t ? t.summary : {};

  const globalRows = [];
  TF_ORDER.forEach(k => {
    const tk = d.tfs[k];
    if (tk) (tk.rows || []).forEach(r => globalRows.push(Object.assign({}, r, { tf: k })));
  });
  globalRows.sort((a, b) => b.score - a.score);
  const top20 = globalRows.slice(0, 20);

  TF_ORDER.forEach(k => {
    const el = $(`#tab-${k}`);
    if (el) {
      const b = el.querySelector(".tab-badge");
      if (b) {
        const n = (d.tfs[k] && d.tfs[k].summary.acao) || 0;
        b.textContent = n || "";
        b.style.display = n ? "" : "none";
      }
    }
  });

  const focus = sum.focus || [];

  const hero = `
    <section class="hero" style="grid-template-columns:1.5fr 1fr;margin-bottom:16px">
      <div class="card price-card">
        <h3><span class="dot"></span> Sinais de pré-pump agora</h3>
        <div class="price-main">
          <span style="font-size:26px;font-weight:800">${sum.total_acao || 0}</span>
          <span class="pill green">AÇÃO (setup pronto)</span>
        </div>
        <div class="price-sub">
          <span class="mini-stat">Observar <b>${sum.total_obs || 0}</b></span>
          <span class="mini-stat">Melhor setup <b>${focus[1] || "—"}</b></span>
          <span class="mini-stat">Timeframe <b>${focus[0] ? TF_LABEL[focus[0]] : "—"}</b></span>
        </div>
      </div>
      <div class="card">
        <h3><span class="dot"></span> Como ler</h3>
        <div class="liq-note" style="font-size:13px;line-height:1.75">
          O radar procura <b class="up">o padrão que antecede o pump</b>, não o pump pronto.<br/>
          <span class="ssg">Rompimento</span> da consolidação com volume · <span class="ssv">volume súbito</span>
          saindo do nada · <span class="ssr">força relativa</span> vs BTC · <span class="ssn">ativos jovens</span> recém-listados.<br/>
          <span class="muted">Score alto ⇒ o setup está montado. Não é garantia — sempre confirme a vela e o volume na hora.</span>
        </div>
      </div>
    </section>

    <div class="card chart-card" style="padding:0;overflow:hidden;margin-bottom:18px">
      ${renderTable("GERAL", top20, null, true, "TOP 20 GERAL — melhores pré-pumps em todos os timeframes")}
    </div>

    <div class="tabs" style="margin-bottom:14px">
      ${TF_ORDER.map(k => `
        <button class="tab ${k === tf ? "active" : ""}" data-tf="${k}" id="tab-${k}">
          ${k} <span class="tab-badge" style="display:none"></span>
        </button>`).join("")}
    </div>

    <div class="card chart-card" style="padding:0;overflow:hidden">
      ${renderTable(tf, rows, ts, false, `TOP 20 — ${TF_LABEL[tf]}`)}
    </div>

    <div class="card" style="margin-top:18px">
      <div class="liq-note" style="margin:0;font-size:12.5px">
        ⚠️ Ferramenta informativa baseada em dados públicos da corretora. "Score" combina leitura estatística de
        acumulação, volume e força relativa — <b>não prevê o futuro</b> nem garante pump. É um radar de setups:
        o que mais tem chance de mover tem mais sinais ativos, mas todo setup pode falhar (volume some, BTC vira, notícia atropela).
        Nunca invista o que não pode perder.
      </div>
    </div>`;

  $("#view").innerHTML = hero;
  document.querySelectorAll(".tab").forEach(b =>
    b.onclick = () => { state.active = b.dataset.tf; renderChipsActive(); drawView(); });
  renderChipsActive();
  requestAnimationFrame(() => drawSparks());
}

function renderChipsActive() {
  return;
}

function renderTable(tf, rows, ts, withTf, title) {
  const rows20 = rows.slice(0, 20);
  if (!rows20.length) {
    return `
      <div style="padding:40px;text-align:center;color:var(--muted)">
        <p style="font-size:18px;margin-bottom:8px">Nenhum sinal acima do corte neste timeframe.</p>
        <p style="font-size:13px">O mercado pode estar sem acumulação agora — cheque as outras abas ou espere a próxima varredura.</p>
      </div>`;
  }
  return `
    <div class="table-title">${title || "TOP 20"} <span class="muted" style="font-weight:400">por score</span></div>
    <table class="radar-table">
      <thead>
        <tr>
          <th>#</th><th>Moeda</th>${withTf ? "<th>TF</th>" : ""}<th>Preço</th><th>Idade</th>
          <th>Consolid.</th><th>Rompim.</th><th>Volume</th><th>VS BTC</th><th>24h</th>
          <th>Score</th><th>Sinais</th><th>Curva</th><th>Status</th>
        </tr>
      </thead>
      <tbody>
        ${rows20.map((r, i) => rowHTML(r, i, withTf)).join("")}
      </tbody>
    </table>`;
}

function rowHTML(r, i, withTf) {
  const sigs = (r.sig || []).map(k => {
    const [label, cls] = SIG_META[k] || [k, "ssg"];
    return `<span class="sig-chip ${cls}">${label}</span>`;
  }).join(" ");
  const status = STATUS_META[r.status] || STATUS_META.VIGIA;
  const age = r.age == null ? "—" : (r.age <= 7 ? `novo (${r.age}d)` : `${r.age}d`);
  const squeezeCls = r.squeeze <= 15 ? "up" : r.squeeze <= 30 ? "" : "down";
  const breakCls = r.break_pct > 0 ? "up" : r.break_pct < -3 ? "down" : "muted";
  const greenDot = r.green ? "●" : "○";
  const breakTxt = r.break_pct >= 0 ? "+" : "";
  const tfCell = withTf ? `<td><span class="tf-pill">${r.tf || ""}</span></td>` : "";
  const sparkData = encodeURIComponent(JSON.stringify(r.spark || []));
  return `
    <tr>
      <td class="muted">${i + 1}</td>
      <td><b>${r.s.replace("USDT", "")}</b> <span class="muted" style="font-size:10px">${greenDot}</span></td>
      ${tfCell}
      <td>${fmtU.format(r.price)}</td>
      <td class="${r.age != null && r.age <= 7 ? "up" : "muted"}">${age}</td>
      <td class="${squeezeCls}">${r.squeeze.toFixed(1)}%</td>
      <td class="${breakCls}">${breakTxt}${r.break_pct.toFixed(2)}%</td>
      <td class="up">×${r.vol_ratio.toFixed(1)}</td>
      <td class="${r.rs >= 0 ? "up" : "down"}">${r.rs >= 0 ? "+" : ""}${r.rs.toFixed(1)}%</td>
      <td class="${r.today24 >= 0 ? "up" : "down"}">${r.today24 >= 0 ? "+" : ""}${r.today24.toFixed(1)}%</td>
      <td>
        <div class="scorebar"><i style="width:${Math.min(100, r.score)}%"></i></div>
        <span class="score-txt">${Math.round(r.score)}</span>
      </td>
      <td><div class="sig-row">${sigs}</div></td>
      <td><canvas class="spark" data-spark="${sparkData}" data-status="${r.status}" data-tf="${r.tf || state.active}" width="" height=""></canvas></td>
      <td><span class="${status[1]}">${status[0]}</span></td>
    </tr>`;
}

function drawSparks() {
  document.querySelectorAll("canvas.spark").forEach((cv) => {
    let vals;
    try { vals = JSON.parse(decodeURIComponent(cv.dataset.spark)); } catch (_) { return; }
    if (!vals || vals.length < 2) return;
    const status = cv.dataset.status || "VIGIA";
    const dpr = window.devicePixelRatio || 1;
    const w = 96, h = 30;
    cv.width = w * dpr; cv.height = h * dpr;
    const ctx = cv.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const color = status === "ACAO" ? "#22d38a" : "#fb923c";
    const min = Math.min(...vals), max = Math.max(...vals), span = max - min || 1;
    const step = w / (vals.length - 1);
    const pts = vals.map((v, i) => [i * step, h - 3 - ((v - min) / span) * (h - 8)]);
    const g = ctx.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, hexA(color, .35)); g.addColorStop(1, hexA(color, 0));
    ctx.beginPath(); ctx.moveTo(pts[0][0], h); pts.forEach(p => ctx.lineTo(p[0], p[1]));
    ctx.lineTo(pts[pts.length - 1][0], h); ctx.closePath(); ctx.fillStyle = g; ctx.fill();
    ctx.beginPath(); pts.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    ctx.strokeStyle = color; ctx.lineWidth = 1.6; ctx.stroke();
    ctx.fillStyle = color; ctx.beginPath();
    ctx.arc(pts[pts.length - 1][0], pts[pts.length - 1][1], 2.2, 0, Math.PI * 2); ctx.fill();
  });
}

const HEX = {};
function hexA(hex, a) {
  const k = hex + a;
  if (!HEX[k]) {
    const h = hex.replace("#", "");
    HEX[k] = `rgba(${parseInt(h.slice(0, 2), 16)},${parseInt(h.slice(2, 4), 16)},${parseInt(h.slice(4, 6), 16)},${a})`;
  }
  return HEX[k];
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._tm);
  t._tm = setTimeout(() => t.classList.remove("show"), 4000);
}

/* ---------------------------------------------------------------- live */
setInterval(async () => {
  const d = await fetchScan(false, state.ex);
  if (d && d.ok) {
    const changed = TF_ORDER.some(tf =>
      d.tfs[tf] && d.tfs[tf].ts && d.tfs[tf].ts !== state.renderTs[tf]);
    if (changed) {
      state.data = d;
      TF_ORDER.forEach(tf => { if (d.tfs[tf]) state.renderTs[tf] = d.tfs[tf].ts; });
      drawView();
    } else if (JSON.stringify(d.summary) !== JSON.stringify((state.data || {}).summary)) {
      state.data = d;
    }
  }
  updateStatus();
}, 5000);

$("#rescan").addEventListener("click", async () => {
  $("#rescan").disabled = true;
  $("#rescan").textContent = "Varrendo...";
  const d = await fetchScan(true, state.ex);
  if (d) {
    setTimeout(async () => {
      const nd = await fetchScan(false, state.ex);
      if (nd && nd.ok) { state.data = nd; drawView(); }
      $("#rescan").disabled = false;
      $("#rescan").textContent = "Varredura agora";
    }, 2000);
  } else {
    $("#rescan").disabled = false;
    $("#rescan").textContent = "Varredura agora";
  }
});

setInterval(updateStatus, 1000);

(async function boot() {
  const d = await fetchScan(false, "mexc");
  if (d && d.ok) {
    state.ex = d.ex || "mexc";
    state.data = d;
    const ready = async () => {
      const nd = await fetchScan(false, state.ex);
      if (nd && nd.ok) {
        state.data = nd;
        const anyRows = TF_ORDER.some(tf => nd.tfs[tf] && nd.tfs[tf].rows.length);
        if (anyRows) {
          drawView();
        } else {
          setTimeout(ready, 3000);
        }
      } else {
        setTimeout(ready, 3000);
      }
    };
    const anyRows = d.tfs && TF_ORDER.some(tf => d.tfs[tf] && d.tfs[tf].rows.length);
    if (anyRows) drawView(); else setTimeout(ready, 2500);
  }
})();