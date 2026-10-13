#!/bin/bash
set -e

echo "============================================"
echo "   🎮 FF BOT - Iniciando servicios"
echo "============================================"

export PORT="${PORT:-8080}"
echo "[i] Puerto web: $PORT"
echo "[i] DB_PATH: ${DB_PATH:-/data/ffbot.db}"

# Inicializar base de datos antes de arrancar
python -c "import database as db; db.init_db(); db.init_exp_history(); print('[i] DB inicializada:', db.DB_PATH)"

# Arrancar el panel web en background
echo "[i] Iniciando panel web..."
python web_panel.py &
WEB_PID=$!

sleep 3

# Arrancar el bot en background
echo "[i] Iniciando bot..."
python Main.py &
BOT_PID=$!

echo "[i] Panel PID=$WEB_PID | Bot PID=$BOT_PID"

# Cierre limpio al recibir SIGTERM/SIGINT
trap "echo '[!] Deteniendo...'; kill $WEB_PID $BOT_PID 2>/dev/null; exit 0" SIGTERM SIGINT

# Esperar a que cualquiera de los dos procesos muera
wait -n $WEB_PID $BOT_PID
