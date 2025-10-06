import csv
import os
import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime

# =====================================================
# CONFIGURACIÓN
# =====================================================
BASE_URL = "https://www.dgae-siae.unam.mx/educacion/carreras.php"
DATA_DIR = Path("data")
SNAP_DIR = Path("snapshots")

DATA_DIR.mkdir(exist_ok=True)
SNAP_DIR.mkdir(exist_ok=True)

# =====================================================
# FUNCIONES AUXILIARES
# =====================================================
def fetch(url: str) -> str:
    """Descarga HTML desde una URL y devuelve el texto."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text


def save_text(content: str, path: Path):
    """Guarda texto en un archivo."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def parse_catalog_table(html: str):
    """Intenta parsear la tabla principal de planes de estudio."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")

    if not table:
        return []

    rows = []
    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    for tr in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) == len(headers):
            row = dict(zip(headers, cells))
            row["raw"] = " | ".join(cells)
            rows.append(row)
    return rows


# =====================================================
# FUNCIÓN PRINCIPAL
# =====================================================
def main():
    try:
        print("[1/2] Descargando catálogo de prueba…")
        html = fetch(BASE_URL)
        save_text(html, SNAP_DIR / "catalog_prueba.html")

        print("[2/2] Parseando tabla del catálogo…")
        rows = parse_catalog_table(html)

        if rows:
            out = DATA_DIR / "snapshot_web_raw.csv"
            cols = [
                "Entidad Responsable",
                "Denominación del Plan de Estudios",
                "Periodo",
                "Modalidad",
                "raw",
            ]
            with open(out, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                w.writerows(rows)
            print(f"✅ Guardado {out} con {len(rows)} filas.")
        else:
            print("⚠️ No logré extraer filas todavía. Revisa snapshots/catalog_prueba.html")

        print("Listo ✔")

    except Exception as e:
        # Si algo falla (como red bloqueada o página caída), no rompe el flujo
        print(f"⚠️ Scraper no pudo completar (posible bloqueo/red): {e}")
        print("Continuo sin actualizar datos esta corrida.")


if __name__ == "__main__":
    main()
