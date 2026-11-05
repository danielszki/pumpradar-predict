#!/bin/bash
# Build do .deb do PumpRadar Predict
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
VER="1.0.0"
PKG="pumpradar-predict"
STAGE="$ROOT/build/pkg"
DEB="$ROOT/build/${PKG}_${VER}_all.deb"

rm -rf "$ROOT/build"
mkdir -p "$STAGE/opt/pumpradar-predict/web" \
         "$STAGE/usr/bin" \
         "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/icons/hicolor/256x256/apps" \
         "$STAGE/DEBIAN"

# ---------- app ----------
cp "$ROOT/src/server.py" "$STAGE/opt/pumpradar-predict/server.py"
cp "$ROOT/src/app.py" "$STAGE/opt/pumpradar-predict/app.py"
cp "$ROOT/src/web/index.html" "$ROOT/src/web/style.css" "$ROOT/src/web/app.js" "$STAGE/opt/pumpradar-predict/web/"
python3 "$ROOT/make_icon.py" "$STAGE/opt/pumpradar-predict/pumpradar.png"
cp "$STAGE/opt/pumpradar-predict/pumpradar.png" "$STAGE/opt/pumpradar-predict/web/pumpradar.png"
python3 "$ROOT/make_icon.py" "$STAGE/usr/share/icons/hicolor/256x256/apps/pumpradar-predict.png"

# ---------- launcher ----------
cat > "$STAGE/usr/bin/pumpradar-predict" <<'EOF'
#!/bin/sh
exec python3 /opt/pumpradar-predict/app.py "$@"
EOF
chmod +x "$STAGE/usr/bin/pumpradar-predict"

# ---------- desktop entry ----------
cat > "$STAGE/usr/share/applications/pumpradar-predict.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=PumpRadar Predict
GenericName=Radar de Setups Pre-Pump
Comment=Varre todos os perps USDT da MEXC em 5 timeframes e acha os setups pre-pump: acumulação + rompimento com volume, volume súbito e força relativa vs BTC (auto-refresh 5min)
Exec=/usr/bin/pumpradar-predict
Icon=pumpradar-predict
Terminal=false
Categories=Finance;Utility;Office;
Keywords=crypto;futures;mexc;radar;predict;setup;breakout;
EOF

# ---------- control ----------
cat > "$STAGE/DEBIAN/control" <<EOF
Package: $PKG
Version: $VER
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.7), python3-gi, gir1.2-gtk-3.0, gir1.2-webkit2-4.1 | gir1.2-webkit2-4.0
Maintainer: PumpRadar Predict <dev@pumpradar.local>
Description: Radar de setups pre-pump (perpétuos USDT da MEXC)
 Mesma cara do PumpRadar, mas apontando para o OUTRO lado do trade:
 em vez de achar quem já caiu, varre sozinho os perpétuos USDT da MEXC
 em 5 timeframes (5m/15m/1h/4h/1d) e ranqueia os setups clássicos que
 ANTECEDEM o pump: acumulação apertada + rompimento de resistência com
 volume, volume súbito, força relativa vs BTC e ativos jovens.
 Atualização automática a cada 5 minutos. Janela nativa (WebKitGTK).
EOF

# ---------- build ----------
dpkg-deb --root-owner-group --build "$STAGE" "$DEB"
echo
echo "✔ Pacote criado: $DEB"
echo "  Instale com:  sudo dpkg -i $DEB (use sudo apt install -f -y antes se reclamar)"
echo "  Execute com:  pumpradar-predict"
