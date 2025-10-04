# clean_snapshot.py
import re
import pandas as pd
from pathlib import Path

RAW_PATH = Path("data/snapshot_web_raw.csv")
OUT_PATH = Path("data/snapshot_web.csv")

MODALIDADES_CATALOG = [
    "ESCOLARIZADO",
    "ABIERTA",
    "A DISTANCIA",
    "A DISTANCIA (SUAYED)",
    "SUAYED",
    "MIXTA",
    "SEMIESCOLARIZADA",
    "ABIERTA Y A DISTANCIA",
]

PERIODO_RE = re.compile(r"\b(20\d{2}-[12])\b")
PLANTEL_RE = re.compile(r"PLANTEL:\s*\[\d+\]\s*-\s*([^\|\n\r]+)", re.IGNORECASE)
CARRERA_RE = re.compile(r"\b\d{2,4}\s+([A-ZÁÉÍÓÚÑÜ0-9\-\s]{6,}?)\s+(20\d{2}-[12])", re.IGNORECASE)

def norm(s):
    return str(s).strip()

def norm_up(s):
    return norm(s).upper()

def guess_periodo(row):
    # 1) Si la columna Periodo ya parece válida, úsala
    p = str(row.get("Periodo", "")).strip()
    m = PERIODO_RE.search(p)
    if m:
        return m.group(1)
    # 2) Busca en raw
    raw = str(row.get("raw", ""))
    m = PERIODO_RE.search(raw)
    return m.group(1) if m else ""

def guess_modalidad(row):
    # 1) Usa la columna si está bien
    mod = norm_up(row.get("Modalidad", ""))
    if any(m in mod for m in [m for m in MODALIDADES_CATALOG]):
        return mod
    # 2) Busca en raw
    raw = norm_up(row.get("raw", ""))
    for m in MODALIDADES_CATALOG:
        if m in raw:
            return m
    return ""

def guess_entidad(row):
    # 1) Usa la columna si es útil
    ent = norm(row.get("Entidad Responsable", ""))
    if ent and "PLANTEL" not in ent.upper():
        return ent
    # 2) Regex PLANTEL: [xxx] - NOMBRE
    raw = str(row.get("raw", ""))
    m = PLANTEL_RE.search(raw)
    if m:
        return norm(m.group(1))
    # 3) Fallback: primer segmento del raw antes de "|"
    if "|" in raw:
        return norm(raw.split("|", 1)[0])
    return ""

def guess_carrera(row, periodo):
    # 1) Usa la columna si se ve como nombre de plan/carrera
    car = norm(row.get("Denominación del Plan de Estudios", ""))
    if car and not any(k in car.upper() for k in ["PLANTEL", "CARRERA", "PERIODO", "MODALIDAD"]):
        return car
    # 2) Regex basada en “… <clave> <CARRERA EN MAYÚSCULAS> <PERIODO> …”
    raw = str(row.get("raw", ""))
    m = CARRERA_RE.search(raw)
    if m:
        return norm(m.group(1))
    # 3) Fallback: si tenemos el periodo, toma el bloque anterior al periodo
    if periodo and periodo in raw:
        left = raw.split(periodo)[0]
        # quita posible entidad a la izquierda
        if "|" in left:
            left = left.split("|")[-1]
        return norm(left)
    return ""

def canonical_id(ent, car, mod):
    return f"{norm_up(ent)} | {norm_up(car)} | {norm_up(mod)}"

def main():
    if not RAW_PATH.exists():
        raise SystemExit(f"No encuentro {RAW_PATH}. Corre primero: python scraper.py")

    df = pd.read_csv(RAW_PATH, dtype=str).fillna("")
    cleaned = []

    for _, row in df.iterrows():
        periodo = guess_periodo(row)
        modalidad = guess_modalidad(row)
        entidad = guess_entidad(row)
        carrera = guess_carrera(row, periodo)

        if not carrera or not entidad or not periodo:
            # descarta filas ruidosas
            continue

        item = {
            "Entidad Responsable": entidad.strip(),
            "Denominación del Plan de Estudios": carrera.strip(),
            "Modalidad": modalidad.strip(),
            "Periodo": periodo.strip(),
        }
        item["ID_CANONICO"] = canonical_id(
            item["Entidad Responsable"],
            item["Denominación del Plan de Estudios"],
            item["Modalidad"],
        )
        cleaned.append(item)

    out = pd.DataFrame(cleaned).drop_duplicates()
    # ordena y normaliza espacios
    for c in ["Entidad Responsable","Denominación del Plan de Estudios","Modalidad","Periodo","ID_CANONICO"]:
        out[c] = out[c].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()

    out = out.sort_values(["Entidad Responsable","Denominación del Plan de Estudios","Periodo"]).reset_index(drop=True)
    OUT_PATH.parent.mkdir(exist_ok=True)
    out.to_csv(OUT_PATH, index=False, encoding="utf-8")
    print(f"✅ Limpieza lista: {OUT_PATH} con {len(out)} filas.")

if __name__ == "__main__":
    main()
