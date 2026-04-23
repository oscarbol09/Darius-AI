#!/bin/bash
# startup.sh — Comando de inicio para Azure App Service (Linux)
# ──────────────────────────────────────────────────────────────
# Azure expone el puerto 8000 internamente y lo mapea al 80/443 público.
# --server.address 0.0.0.0 es obligatorio para que Azure pueda hacer
# el proxy inverso hacia el contenedor.

python -m streamlit run app.py --server.port 8000 --server.address 0.0.0.0
