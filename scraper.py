# scraper.py
import os
import time
import csv
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# === URL de catálogo de prueba (contiene plantel/carrera/periodo/modalidad) ===
BASE_URL = "https://www.dgae-siae.unam.mx/www_cat.php?caus=59&prd1=2250&prd2=2251"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SIAE-updater/0.1)"}

# Carpetas de salida
DATA_DIR = Path("data")
SNAP_DIR = Path("snapshots")
DATA_DIR.mkdir(exist_ok=True)
SNAP_DIR.mkdir(exist_ok=True)

def fetch(url: str) -> str:
    """Descarga HTML en texto (con encoding seguro)."""
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.encoding = r.apparent_encoding or "utf-8"
    r.raise_for_status()
    return r.text

def save_text(text: str, path: Path):
    path.write_text(text, encoding="utf-8")

def parse_catalog_table(html: str) -> list[dict]:
    """
    Intenta parsear catálogos tipo www_cat.php que suelen tener columnas:
    PLANTEL / CARRERA / PERIODO / MODALIDAD / (SEMESTRES)
    Si no lo logra, regresa lista vacía (no falla).
    """
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    # Busca tablas
    tables = soup.find_all("table")
    for tb in tables:
        for tr in tb.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
            if not cells or len(cells) < 3:
                continue

            # Heurística mínima: si parece una fila con info útil
            text = " | ".join(cells)
            if any(k in text.upper() for k in ["PLANTEL", "CARRERA", "PERIODO", "MODALIDAD"]) or len(cells) >= 4:
                rows.append({"raw": text})

    if not rows:
        return []

    # Separación básica por posición (afinaremos en el siguiente paso)
    parsed = []
    for r in rows:
        parts = [p.strip() for p in r["raw"].split("|")]
        d = {
            "Entidad Responsable": parts[0] if len(parts) > 0 else "",
            "Denominación del Plan de Estudios": parts[1] if len(parts) > 1 else "",
            "Periodo": parts[2] if len(parts) > 2 else "",
            "Modalidad": parts[3] if len(parts) > 3 else "",
            "raw": r["raw"],
        }
        parsed.append(d)
    return parsed

def main():
    print("[1/2] Descargando catálogo de prueba…")
    html = fetch(BASE_URL)
    save_text(html, SNAP_DIR / "catalog_prueba.html")

    print("[2/2] Parseando tabla del catálogo…")
    rows = parse_catalog_table(html)

    if rows:
        out = DATA_DIR / "snapshot_web_raw.csv"
        cols = ["Entidad Responsable", "Denominación del Plan de Estudios", "Periodo", "Modalidad", "raw"]
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"✅ Guardado {out} con {len(rows)} filas.")
    else:
        print("⚠️ No logré extraer filas todavía. Revisa el HTML guardado en snapshots/catalog_prueba.html")

    print("Listo ✔")

if __name__ == "__main__":
    main()
