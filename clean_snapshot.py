# clean_snapshot.py
import re
import pandas as pd
from pathlib import Path

# Rutas de entrada/salida
RAW_PATH = Path("data/snapshot_web_raw.csv")
OUT_PATH = Path("data/snapshot_web.csv")

# Catálogo simple de modalidades (ajústalo si detectas variantes)
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

# Patrones útiles
PERIODO_RE = re.compile(r"\b(20\d{2}-[12])\b")
PLANTEL_RE = re.compile(r"PLANTEL:\s*\[\d+\]\s*-\s*([^\|\n\r]+)", re.IGNORECASE)
CARRERA_RE = re.compile(r"\b\d{2,4}\s+([A-ZÁÉÍÓÚÑÜ0-9\-\s]{6,}?)\s+(20\d{2}-[12])", re.IGNORECASE)

def norm(s):
    return str(s).strip()

def norm_up(s):
    return norm(s).upper()

def guess_periodo(row):
    # 1) Usa la columna si ya trae formato válido
    p = str(row.get("Periodo", "")).strip()
    m = PERIODO_RE.search(p)
    if m:
        return m.group(1)
    # 2) Busca en raw
    raw = str(row.get("raw", ""))
    m = PERIODO_RE.search(raw)
    return m.group(1) if m else ""

def guess_modalidad(row):
    # 1) Usa la columna si coincide con el catálogo
    mod = norm_up(row.get("Modalidad", ""))
    if any(m in mod for m in MODALIDADES_CATALOG):
        return mod
    # 2) Busca en raw
    raw = norm_up(row.get("raw", ""))
    for m in MODALIDADES_CATALOG:
        if m in raw:
            return m
    return ""

def guess_entidad(row):
    # 1) Usa la columna si no parece encabezado
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
    # 1) Usa la columna si luce como nombre de plan/carrera
    car = norm(row.get("Denominación del Plan de Estudios", ""))
    if car and not any(k in car.upper() for k in ["PLANTEL", "CARRERA", "PERIODO", "MODALIDAD"]):
        return car
    # 2) Regex “… <clave> <CARRERA> <PERIODO> …”
    raw = str(row.get("raw", ""))
    m = CARRERA_RE.search(raw)
    if m:
        return norm(m.group(1))
    # 3) Si tenemos periodo, toma bloque previo
    if periodo and periodo in raw:
        left = raw.split(periodo)[0]
        if "|" in left:
            left = left.split("|")[-1]
        return norm(left)
    return ""

def canonical_id(ent, car, mod):
    return f"{norm_up(ent)} | {norm_up(car)} | {norm_up(mod)}"

def main():
    # ✅ Tolerante: si no hay CSV crudo o está vacío, crear salida vacía y terminar OK
    if not RAW_PATH.exists() or RAW_PATH.stat().st_size < 5:
        OUT_PATH.parent.mkdir(exist_ok=True)
        pd.DataFrame(columns=[
            "Entidad Responsable",
            "Denominación del Plan de Estudios",
            "Modalidad",
            "Periodo",
            "ID_CANONICO",
        ]).to_csv(OUT_PATH, index=False, encoding="utf-8")
        print(f"⚠️ No hay datos crudos. Creé {OUT_PATH} vacío.")
        return

    # Carga datos crudos
    df = pd.read_csv(RAW_PATH, dtype=str).fillna("")
    cleaned = []

    for _, row in df.iterrows():
        periodo = guess_periodo(row)
        modalidad = guess_modalidad(row)
        entidad = guess_entidad(row)
        carrera = guess_carrera(row, periodo)

        # descarta filas incompletas/ruidosas
        if not carrera or not entidad or not periodo:
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

    # Normaliza espacios y orden
    for c in ["Entidad Responsable","Denominación del Plan de Estudios","Modalidad","Periodo","ID_CANONICO"]:
        out[c] = out[c].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()

    out = out.sort_values(
        ["Entidad Responsable","Denominación del Plan de Estudios","Periodo"]
    ).reset_index(drop=True)

    OUT_PATH.parent.mkdir(exist_ok=True)
    out.to_csv(OUT_PATH, index=False, encoding="utf-8")
    print(f"✅ Limpieza lista: {OUT_PATH} con {len(out)} filas.")

if __name__ == "__main__":
    main()
