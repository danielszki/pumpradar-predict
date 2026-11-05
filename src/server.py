#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PumpRadar Predict — Radar de setups pre-pump (perpétuos USDT).

Varre os perpétuos USDT da MEXC em 4
timeframes e ranqueia as moedas com o padrão clássico que ANTECEDE o pump:
  * Acumulação + rompimento de resistência com volume
  * Volume súbito / início de movimento
  * Força relativa vs BTC
  * Ativos jovens / recém-listados (pump de listagem)

Re-varre o mercado automaticamente a cada SCAN_TTL segundos.
Rodar:  python3 server.py [--port 8766]
"""

import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

MAPI = "https://contract.mexc.com/api/v1"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) PumpRadar-Predict/1.0"}
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

MIN_VOL = 200_000      # volume 24h mínimo em USDT (quote)
SCAN_TTL = 300         # 5 minutos
MIN_SHOW = 45          # score mínimo para aparecer (referência)
TOP_ROWS = 100         # linhas por timeframe guardadas no estado (UI mostra top 20)

TF_CONFIGS = {
    "5m":  {"N": 96, "K": 36, "label": "5m",  "janela": "3h",    "min": 34},
    "15m": {"N": 96, "K": 36, "label": "15m", "janela": "9h",   "min": 36},
    "1h":  {"N": 72, "K": 24, "label": "1h",  "janela": "1 dia", "min": 40},
    "4h":  {"N": 48, "K": 16, "label": "4h",  "janela": "2,5 dias", "min": 45},
    "1d":  {"N": 60, "K": 20, "label": "1d",  "janela": "20 dias", "min": 45},
}
TF_ORDER = ["5m", "15m", "1h", "4h", "1d"]

MEXC_INTERVAL = {"5m": "Min5", "15m": "Min15", "1h": "Min60", "4h": "Hour4", "1d": "Day1"}


def _mexc_parse_klines(data):
    # resposta = {"success":true, "data":{"time":[...], "open":[...], "high":[...], "low":[...], "close":[...], "vol":[...]}}
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        data = data["data"]
    if not isinstance(data, dict):
        return []
    t = data.get("time") or []
    if not t:
        return []
    o = data.get("open") or []
    h = data.get("high") or []
    l = data.get("low") or []
    c = data.get("close") or []
    v = data.get("vol") or []
    n = min(len(t), len(o), len(h), len(l), len(c), len(v))
    return [[t[i], o[i], h[i], l[i], c[i], v[i]] for i in range(n)]


EXCHANGES = {
    "mexc": {
        "label": "MEXC",
        "sym": lambda coin: coin + "_USDT",
        "interval": lambda tf: MEXC_INTERVAL[tf],
        "klines_url": lambda coin, tf, n: "%s/contract/kline/%s_USDT?interval=%s&limit=%d" % (MAPI, coin, MEXC_INTERVAL[tf], n),
        "parse_klines": _mexc_parse_klines,
    },
}


LOCK = threading.Lock()

# Estado por corretora — cada uma tem tfs próprios e flag própria de scan.
STATE = {
    "ex": "mexc",
    "tfs": {ex: {tf: {
        "rows": [], "scanned": 0, "total": 0, "ts": 0.0, "scanning": False,
        "elapsed": 0.0, "err": None, "summary": {},
    } for tf in TF_ORDER} for ex in EXCHANGES},
    "scanning": {ex: [False] for ex in EXCHANGES},
    "ts": {ex: 0.0 for ex in EXCHANGES},
}

# --------------------------------------------------------------------------- #
# Rede: semáforo global + espaçamento — evita bater no rate-limit da corretora #
# --------------------------------------------------------------------------- #
NET_SEM = threading.Semaphore(6)
RATE_LOCK = threading.Lock()
LAST_REQ = [0.0]


def http_get(url, timeout=15):
    retries = 2
    delay = 0.5
    while True:
        with RATE_LOCK:
            gap = time.time() - LAST_REQ[0]
            if gap < 0.05:
                time.sleep(0.05 - gap)
            LAST_REQ[0] = time.time()
        try:
            with NET_SEM:
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 418) and retries > 0:
                retries -= 1
                time.sleep(delay)
                delay = min(delay * 2, 6)
                continue
            raise
        except (urllib.error.URLError, socket.timeout, ConnectionResetError) as e:
            if retries > 0:
                retries -= 1
                time.sleep(delay)
                delay = min(delay * 2, 6)
                continue
            raise


# --------------------------------------------------------------------------- #
# Carga do mercado por corretora                                               #
# --------------------------------------------------------------------------- #
def load_mexc_market():
    # se a listagem falhar não há o que varrer — deixa subir (do_scan seta err)
    tick = http_get("%s/contract/ticker" % MAPI)
    rows = tick.get("data") if isinstance(tick, dict) else tick
    perps = []
    for t in rows or []:
        st = t.get("symbol", "")
        if not st.endswith("_USDT"):
            continue
        vol = float(t.get("amount24", 0) or 0)
        if vol < MIN_VOL:
            continue
        r = float(t.get("riseFallRate", 0) or 0)
        if abs(r) <= 1.5:
            r *= 100
        perps.append({
            "sym": st, "coin": st[:-5],
            "vol24": vol,
            "today24": round(r, 2),
            "onboard": None,
            "funding": t.get("fundingRate"),
        })
    return perps


def load_market(ex):
    return load_mexc_market()


# --------------------------------------------------------------------------- #
# Sinais de setup pré-pump                                                     #
# --------------------------------------------------------------------------- #
def analyze_symbol(ex, m, tf, btc_chg):
    cfg = TF_CONFIGS[tf]
    N, K = cfg["N"], cfg["K"]
    try:
        data = http_get(EXCHANGES[ex]["klines_url"](m["coin"], tf, N))
        ks = EXCHANGES[ex]["parse_klines"](data)
    except Exception:
        return None
    try:
        if len(ks) < K + 4:
            return None
        closes = [float(k[4]) for k in ks]
        opens = [float(k[1]) for k in ks]
        highs = [float(k[2]) for k in ks]
        lows = [float(k[3]) for k in ks]
        vols = [float(k[5]) for k in ks]
        last = closes[-1]
        if last <= 0:
            return None

        seg_high = max(highs[-K - 1:-1])
        seg_low = min(lows[-K - 1:-1])
        seg_vol = sum(vols[-K - 1:-1]) / K
        vol_ratio = vols[-1] / seg_vol if seg_vol > 0 else 0
        squeeze = (seg_high / seg_low - 1) * 100 if seg_low > 0 else 0
        break_pct = (last / seg_high - 1) * 100 if seg_high > 0 else 0

        chg_w = (last / closes[-K - 1] - 1) * 100 if closes[-K - 1] > 0 else 0
        rs = chg_w - btc_chg
        green = closes[-1] > opens[-1]

        # idade: MEXC não expõe listagem em lote — derivamos da
        # primeira vela da série
        onboard_ms = m.get("onboard") or ks[0][0]
        age_days = (time.time() * 1000 - onboard_ms) / 86400000 if onboard_ms else None

        brk = break_pct >= 0.4 and vol_ratio >= 1.4
        burst = vol_ratio >= 2.1
        rsg = rs >= 1.2
        fresh = age_days is not None and age_days <= 45
        squeeze_tight = squeeze <= 40

        score = 0.0
        if brk:
            score += min(36, 12 + break_pct * 5 + (vol_ratio - 1) * 7)
        score += max(0, 14 - squeeze * 2.4)
        if burst:
            score += min(20, (vol_ratio - 1) * 8)
        if rsg:
            score += min(16, rs * 2.5)
        if fresh:
            score += 14 if age_days <= 7 else 10 if age_days <= 30 else 6
        if green:
            score += 5
        if break_pct > 12:
            score -= 14
        if break_pct > 25:
            score -= 22
        if chg_w > 60:
            score -= 14
        if m.get("today24", 0) > 30:
            score -= 10
        score = round(score, 1)

        sig = []
        if brk:
            sig.append("rompimento")
        if burst:
            sig.append("volume")
        if rsg:
            sig.append("rs")
        if fresh:
            sig.append("nova")
        if not sig:
            return None

        path = [round(c, 8) for c in closes[-24:]]

        return {
            "s": m["coin"], "price": last,
            "age": None if age_days is None else round(age_days, 1),
            "squeeze": round(squeeze, 2),
            "break_pct": round(break_pct, 2),
            "vol_ratio": round(vol_ratio, 2),
            "rs": round(rs, 2),
            "today24": round(m.get("today24", 0), 2),
            "score": score,
            "status": status_label(score),
            "sig": sig,
            "spark": path,
            "green": green,
            "vol": m.get("vol24", 0),
            "funding": m.get("funding"),
        }
    except Exception:
        return None


def status_label(score):
    if score >= 62:
        return "ACAO"
    if score >= 42:
        return "OBSERVAR"
    return "VIGIA"


def scan_tf(ex, tf, perps, btc_chg):
    cfg = TF_CONFIGS[tf]
    t0 = time.time()
    rows = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for r in pool.map(lambda m: analyze_symbol(ex, m, tf, btc_chg), perps):
            if r:
                rows.append(r)

    # ranking: do melhor para o pior score (top 20 por timeframe na UI)
    rows.sort(key=lambda r: r["score"], reverse=True)

    total_acao = sum(1 for r in rows if r["score"] >= 62)
    total_obs = sum(1 for r in rows if 42 <= r["score"] < 62)
    foco = max(rows, key=lambda r: r["score"]) if rows else None

    with LOCK:
        STATE["tfs"][ex][tf].update({
            "rows": rows[:TOP_ROWS],
            "scanned": len(rows),
            "total": len(perps),
            "ts": time.time(),
            "elapsed": round(time.time() - t0, 1),
            "scanning": False,
            "err": None,
            "summary": {
                "acao": total_acao,
                "obs": total_obs,
                "top_coin": foco["s"] if foco else None,
                "top_score": foco["score"] if foco else 0,
                "janela": cfg["janela"],
                "min": cfg["min"],
            },
        })


def btc_chg_for(ex, tf):
    # baseline vs BTC no mesmo timeframe (só 1d usa janela maior)
    if tf != "1d":
        return 0.0
    try:
        bks = EXCHANGES[ex]["parse_klines"](
            http_get(EXCHANGES[ex]["klines_url"]("BTC", tf, 3)))
    except Exception:
        return 0.0
    if len(bks) >= 2:
        return (float(bks[-1][4]) / float(bks[0][4]) - 1) * 100
    return 0.0


def start_scan(ex):
    with LOCK:
        if STATE["scanning"][ex][0]:
            return
        STATE["scanning"][ex][0] = True
    threading.Thread(target=do_scan, args=(ex,), daemon=True).start()


def do_scan(ex):
    try:
        perps = load_market(ex)
        threads = []
        for tf in TF_ORDER:
            t = threading.Thread(target=scan_tf, args=(ex, tf, perps, btc_chg_for(ex, tf)), daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        with LOCK:
            STATE["scanning"][ex][0] = False
            STATE["ts"][ex] = time.time()
    except Exception as e:
        with LOCK:
            STATE["scanning"][ex][0] = False
            for tf in TF_ORDER:
                STATE["tfs"][ex][tf]["err"] = "sem conexão com %s" % EXCHANGES[ex]["label"]
        raise


# --------------------------------------------------------------------------- #
# Snapshot no formato que o frontend consome                                   #
# --------------------------------------------------------------------------- #
def snapshot():
    ex = STATE["ex"]
    now = time.time()
    tfs = STATE["tfs"][ex]
    total_acao = total_obs = 0
    focus = None
    with LOCK:
        for tf in TF_ORDER:
            d = tfs[tf]
            if d["summary"]:
                total_acao += d["summary"].get("acao", 0)
                total_obs += d["summary"].get("obs", 0)
                sc = d["summary"].get("top_score", 0)
                if focus is None or sc > focus[2]:
                    focus = (tf, d["summary"].get("top_coin"), sc)
    out = {}
    scanning = False
    for tf in TF_ORDER:
        d = tfs[tf]
        out[tf] = {
            "rows": d["rows"],
            "scanned": d["scanned"],
            "total": d["total"],
            "ts": d["ts"],
            "age": round(max(0, now - d["ts"]), 0) if d["ts"] else 0,
            "scanning": d["scanning"],
            "elapsed": d["elapsed"],
            "err": d["err"],
            "summary": d["summary"],
        }
    scanning = STATE["scanning"][ex][0]
    ex_ts = STATE["ts"][ex]
    age = round(max(0, now - ex_ts), 0) if ex_ts else 0
    # auto-refresh: se passou do TTL, dispara nova varredura desta corretora
    if not scanning and (not ex_ts or now - ex_ts >= SCAN_TTL):
        start_scan(ex)
    return {
        "ok": True,
        "ex": ex,
        "ex_list": list(EXCHANGES),
        "scanning": scanning,
        "ts": ex_ts,
        "age": age,
        "next_in": max(0, round(SCAN_TTL - age, 0)),
        "ttl": SCAN_TTL,
        "tfs": out,
        "tf_order": TF_ORDER,
        "summary": {
            "total_acao": total_acao,
            "total_obs": total_obs,
            "focus": list(focus) if focus else [],
            "min_vol": MIN_VOL,
        },
    }


# --------------------------------------------------------------------------- #
# Servidor HTTP                                                                #
# --------------------------------------------------------------------------- #
CONTENT = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "PumpRadar-Predict/1.0"

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        try:
            u = urllib.parse.urlparse(self.path)
            if u.path == "/api/scan":
                q = urllib.parse.parse_qs(u.query)
                ex = (q.get("ex") or ["mexc"])[0]
                if ex not in EXCHANGES:
                    ex = "mexc"
                force = (q.get("force") or ["0"])[0] == "1"
                with LOCK:
                    STATE["ex"] = ex
                    if force:
                        for tf in TF_ORDER:
                            STATE["tfs"][ex][tf]["ts"] = 0
                        STATE["ts"][ex] = 0.0
                if force:
                    start_scan(ex)  # fora do LOCK (start_scan também pega LOCK)
                self._send(200, json.dumps(snapshot(), ensure_ascii=False).encode(), "application/json; charset=utf-8")
            elif u.path == "/api/health":
                self._send(200, b'{"ok":true}', "application/json")
            else:
                name = "index.html" if u.path in ("/", "/index.html") else u.path.lstrip("/")
                safe = os.path.realpath(os.path.join(WEB_DIR, name))
                if not safe.startswith(os.path.realpath(WEB_DIR)) or not os.path.isfile(safe):
                    self._send(404, b"Not found", "text/plain")
                    return
                ext = os.path.splitext(safe)[1].lower()
                with open(safe, "rb") as f:
                    body = f.read()
                self._send(200, body, CONTENT.get(ext, "application/octet-stream"))
        except BrokenPipeError:
            pass
        except Exception as e:
            try:
                self._send(500, json.dumps({"ok": False, "error": str(e)}).encode(), "application/json")
            except Exception:
                pass
            self.log_message("ERRO: %s" % e)

    def log_message(self, *args):
        pass


class Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    port = 8766
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--port" and i + 1 < len(args):
            port = int(args[i + 1])

    start_scan("mexc")
    srv = Server(("127.0.0.1", port), Handler)
    print("=" * 56, flush=True)
    print("  PumpRadar Predict — Radar de setups pré-pump", flush=True)
    print("  Janela local: http://127.0.0.1:%d/" % port, flush=True)
    print("  Varredura automática a cada 5 minutos (5 timeframes).", flush=True)
    print("  Corretora: MEXC.", flush=True)
    print("  (Feche a janela para encerrar)", flush=True)
    print("=" * 56, flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.server_close()


if __name__ == "__main__":
    main()