#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PumpRadar Predict — janela nativa (WebKitGTK). Fallback p/ navegador se
faltar WebKitGTK. Run: python3 app.py [--browser]"""

import os
import socket
import sys
import threading
import time
import webbrowser

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def start_server(port):
    from server import Handler, Server

    srv = Server(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def try_webkit():
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk  # noqa

        try:
            gi.require_version("WebKit2", "4.1")
        except ValueError:
            gi.require_version("WebKit2", "4.0")
        from gi.repository import WebKit2  # noqa

        return True
    except Exception:
        return False


def run_browser(url):
    webbrowser.open(url)
    print("PumpRadar Predict abrindo no navegador:", url, flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


def run_gtk(url, srv):
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    try:
        gi.require_version("WebKit2", "4.1")
    except ValueError:
        gi.require_version("WebKit2", "4.0")
    from gi.repository import WebKit2

    win = Gtk.Window(title="PumpRadar Predict — Radar de Setups Pré-Pump")
    win.set_default_size(1400, 900)
    win.set_position(Gtk.WindowPosition.CENTER)
    icon = os.path.join(BASE, "pumpradar.png")
    if os.path.exists(icon):
        try:
            win.set_icon_from_file(icon)
        except Exception:
            pass

    web = WebKit2.WebView()
    web.get_settings().set_enable_developer_extras(False)

    def on_close(*_):
        try:
            srv.shutdown()
            srv.server_close()
        except Exception:
            pass
        Gtk.main_quit()

    win.connect("destroy", on_close)
    win.add(web)
    web.load_uri(url)
    win.show_all()
    Gtk.main()


def main():
    force_browser = "--browser" in sys.argv or os.environ.get("PUMPRADAR_BROWSER") == "1"
    port = free_port()
    srv = start_server(port)
    url = "http://127.0.0.1:%d/" % port

    print("=" * 56, flush=True)
    print("  PumpRadar Predict — Radar de setups pré-pump", flush=True)
    print("  Janela local: %s" % url, flush=True)
    print("  (Feche a janela para encerrar)", flush=True)
    print("=" * 56, flush=True)

    if force_browser or not try_webkit():
        if not force_browser:
            print("WebKitGTK não disponível — abrindo no navegador.", flush=True)
        run_browser(url)
    else:
        try:
            run_gtk(url, srv)
        except Exception as e:
            print("Erro ao abrir janela nativa (%s) — navegador." % e, flush=True)
            run_browser(url)


if __name__ == "__main__":
    main()