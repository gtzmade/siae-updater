# scraper.py
import csv
from pathlib import Path
import requests
from bs4 import BeautifulSoup

DATA_DIR = Path("data")
SNAP_DIR = Path("snapshots")
URLS_FILE = Path("urls.txt")

DATA_DIR.mkdir(exist_ok=True)
SNAP_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# URLs por defecto (fallbacks) por si urls.txt está vacío o falla todo
DEFAULT_URLS = [
    "https://www.dgae-siae.unam.mx/www_cat.php?caus=59&prd1=2250&prd2=2251",
    "https://www.dgae-siae.unam.mx/educacion/carreras.php",
]

RAW_OUT = DATA_DIR / "snapshot_web_raw.csv"
HTML_OUT = SNAP_DIR / "catalog_prueba.html"

def load_urls():
    urls = []
    if URLS_FILE.exists():
        for line in URLS_FILE.read_text(encoding="utf-8").splitlines():
            u = line.strip()
            if u and not u.startswith("#"):
                urls.append(u)
    # asegúrate de tener al menos los fallbacks
    if not urls:
        urls = DEFAULT_URLS[:]
    return urls

def fetch(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text

def save_text(text: str, path: Path):
    path.write_text(text, encoding="utf-8")

def parse_table(html: str):
    """Busca una tabla con <th> y devuelve filas mapeadas + 'raw'."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    rows = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(cells) == len(headers) and cells:
            row = dict(zip(headers, cells))
            row["raw"] = " | ".join(cells)
            rows.append(row)
    return rows

def normalize_rows(rows):
    """Mapea a un esquema mínimo común para el paso de limpieza."""
    normed = []
    for r in rows:
        d = {
            "Entidad Responsable": r.get("PLANTEL")
                or r.get("PLANTEL / ENTIDAD")
                or r.get("PLANTEL:")
                or "",
            "Denominación del Plan de Estudios": r.get("CARRERA")
                or r.get("PLAN")
                or r.get("CARRERA / PLAN")
                or "",
            "Periodo": r.get("PERIODO")
                or r.get("PERIODO VIGENTE")
                or "",
            "Modalidad": r.get("MODALIDAD") or "",
            "raw": r.get("raw", ""),
        }
        if any(d.values()):
            normed.append(d)
    return normed

def write_raw(rows):
    cols = ["Entidad Responsable", "Denominación del Plan de Estudios", "Periodo", "Modalidad", "raw"]
    with open(RAW_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})

def main():
    try:
        urls = load_urls()
        collected = []
        last_html = ""

        for url in urls:
            print(f"[scraper] Intentando: {url}")
            try:
                html = fetch(url)
                last_html = html
                rows = parse_table(html)
                if rows:
                    print(f"[scraper] OK: {len(rows)} filas en {url}")
                    collected = normalize_rows(rows)
                    break
            except Exception as e:
                print(f"[scraper] Aviso: fallo al leer {url}: {e}")

        # guarda el último HTML para inspección
        if last_html:
            save_text(last_html, HTML_OUT)

        # SIEMPRE escribe el CSV (puede estar vacío) para que los pasos siguientes no fallen
        write_raw(collected)
        print(f"[scraper] Escribí {RAW_OUT} con {len(collected)} filas.")
        print("Listo ✔")

    except Exception as e:
        print(f"⚠️ Scraper no pudo completar: {e}")
        write_raw([])  # CSV vacío para mantener el pipeline sano
        print(f"[scraper] Generé CSV vacío: {RAW_OUT}")

if __name__ == "__main__":
    main()

