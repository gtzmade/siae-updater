# diff_and_update.py (versión que NO toca "Listado total")
from pathlib import Path
import shutil
import pandas as pd

EXCEL_PATH = Path("19082025_PE Licenciatura_Informe anual - copia (1).xlsx")
HOJA_BASE_BONITA = "Listado total"         # no la tocamos
HOJA_MAESTRA = "Maestra_normalizada"       # nueva hoja técnica
HOJA_CAMBIOS = "Cambios_detectados"
SNAP_PATH = Path("data/snapshot_web.csv")  # limpio desde clean_snapshot.py

def norm_up(s: str) -> str:
    return str(s).strip().upper()

def canonical_id(ent, car, mod):
    return f"{norm_up(ent)} | {norm_up(car)} | {norm_up(mod)}"

def backup_file(path: Path) -> Path:
    bak = path.with_suffix(".backup.xlsx")
    shutil.copy2(path, bak)
    return bak

def main():
    if not EXCEL_PATH.exists():
        raise SystemExit(f"No encuentro el Excel: {EXCEL_PATH}")
    if not SNAP_PATH.exists():
        raise SystemExit(f"No encuentro el snapshot limpio: {SNAP_PATH}. Corre antes: python clean_snapshot.py")

    # --- Lee snapshot web limpio (ya trae columnas planas)
    web = pd.read_csv(SNAP_PATH, dtype=str).fillna("")

    # --- Construye tabla de cambios básica respecto a la Maestra previa (si existe)
    #     Intentamos leer la hoja técnica anterior para detectar "añadidos" y "modificados" respecto a la última corrida.
    try:
        prev = pd.read_excel(EXCEL_PATH, sheet_name=HOJA_MAESTRA, dtype=str).fillna("")
        have_prev = True
    except Exception:
        prev = pd.DataFrame(columns=["Entidad Responsable","Denominación del Plan de Estudios","Modalidad","Periodo","ID_CANONICO"])
        have_prev = False

    # NUEVOS
    nuevos = web[~web["ID_CANONICO"].isin(prev.get("ID_CANONICO", []))].copy()
    nuevos["TipoCambio"] = "NUEVO PE"

    # MODIFICACION PERIODO (para IDs que ya existían)
    mod = prev.merge(web[["ID_CANONICO","Periodo"]], on="ID_CANONICO", how="inner", suffixes=("_prev","_web"))
    modificados = mod[mod["Periodo_prev"] != mod["Periodo_web"]][["ID_CANONICO","Periodo_prev","Periodo_web"]].copy()
    modificados["TipoCambio"] = "MODIFICACION PERIODO"

    # RENOMBRE ENTIDAD (misma carrera+modalidad, cambia entidad)
    prev_cm = prev.assign(
        Carrera_norm=prev["Denominación del Plan de Estudios"].str.upper().str.strip(),
        Modalidad_norm=prev["Modalidad"].astype(str).str.upper().str.strip(),
        Entidad_norm=prev["Entidad Responsable"].astype(str).str.upper().str.strip(),
    )[["Carrera_norm","Modalidad_norm","Entidad_norm"]]

    web_cm = web.assign(
        Carrera_norm=web["Denominación del Plan de Estudios"].str.upper().str.strip(),
        Modalidad_norm=web["Modalidad"].astype(str).str.upper().str.strip(),
        Entidad_norm=web["Entidad Responsable"].astype(str).str.upper().str.strip(),
    )[["Carrera_norm","Modalidad_norm","Entidad_norm"]]

    ren = prev_cm.merge(web_cm, on=["Carrera_norm","Modalidad_norm"], suffixes=("_prev","_web"))
    renombrados = ren[ren["Entidad_norm_prev"] != ren["Entidad_norm_web"]].copy()
    renombrados = renombrados.rename(columns={
        "Carrera_norm": "Denominación del Plan de Estudios (norm)",
        "Modalidad_norm": "Modalidad (norm)",
        "Entidad_norm_prev": "Entidad Responsable (prev)",
        "Entidad_norm_web": "Entidad Responsable (web)",
    })
    renombrados["TipoCambio"] = "RENOMBRE ENTIDAD"

    # Tabla de cambios
    cambios = pd.DataFrame()
    if not nuevos.empty:
        cambios = pd.concat([cambios, nuevos[[
            "ID_CANONICO","Entidad Responsable","Denominación del Plan de Estudios","Modalidad","Periodo","TipoCambio"
        ]]], ignore_index=True)
    if not modificados.empty:
        cambios = pd.concat([cambios, modificados], ignore_index=True)
    if not renombrados.empty:
        cambios = pd.concat([cambios, renombrados], ignore_index=True)

    # --- Guardar: backup + escribir MAESTRA y CAMBIOS, sin tocar "Listado total"
    bak = backup_file(EXCEL_PATH)
    print(f"Backup creado: {bak.name}")

    with pd.ExcelWriter(EXCEL_PATH, engine="openpyxl", mode="a", if_sheet_exists="replace") as xw:
        web.to_excel(xw, sheet_name=HOJA_MAESTRA, index=False)  # hoja técnica estable
        if cambios.empty:
            pd.DataFrame([{"Mensaje": "Sin cambios detectados"}]).to_excel(
                xw, sheet_name=HOJA_CAMBIOS, index=False
            )
        else:
            cambios.to_excel(xw, sheet_name=HOJA_CAMBIOS, index=False)

    print(f"✅ Escribí: '{HOJA_MAESTRA}' (tabla técnica) y '{HOJA_CAMBIOS}'.")
    print("ℹ️ 'Listado total' quedó intacta (no tocada).")

if __name__ == "__main__":
    main()
