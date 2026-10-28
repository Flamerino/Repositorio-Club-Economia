"""Actualiza todas las fuentes que se guardan solo en el repo (no en la base ni en la página).

Lo corre GitHub Actions todos los lunes. Cada fuente es independiente: si una falla, deja un
aviso y sigue con las demás. Después src/exportar_archivos.py las publica en datos/.

PARA SUMAR UNA FUENTE NUEVA:
  1. Crear src/<fuente>/actualizar.py que escriba data/processed/<fuente>/series.csv y
     observaciones.csv (área de trabajo de la corrida) y valide los datos antes de guardar.
  2. Agregar <fuente> a SOLO_REPO en src/almacen.py (mientras no se quiera mostrar en la página).
  3. Agregar el script a FUENTES, abajo, con las carpetas de data/raw/ que escribe (archivos
     originales que se versionan). No hace falta tocar el workflow.

Uso: python src/actualizar_solo_repo.py
"""
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FUENTES = {  # script: carpetas de data/raw/ que escribe (el workflow las commitea)
    "src/datos_gob/actualizar.py": ["data/raw/datos_gob", "data/raw/indec/salarios"],
    "src/mercados/actualizar.py": ["data/raw/mercados"],
    "src/banco_mundial/actualizar.py": ["data/raw/banco_mundial/indicadores"],
    "src/internacional/actualizar.py": ["data/raw/internacional", "data/raw/maddison"],
    "src/opinion/actualizar.py": [],
    "src/bcra/balance_cambiario.py": [],
    "src/bcra/rem.py": [],
    "src/indec/distribucion.py": [],
}
LISTA_RUTAS = RAIZ / ".rutas_solo_repo"  # la lee el workflow para saber qué commitear


def main():
    fallas = []
    for script in FUENTES:
        print(f"\n===== {script}", flush=True)
        try:
            r = subprocess.run([sys.executable, str(RAIZ / script)], cwd=RAIZ, timeout=8 * 60)
            codigo = r.returncode
        except subprocess.TimeoutExpired:
            codigo = "tiempo agotado (8 min)"
        if codigo != 0:
            fallas.append(script)
            print(f"::warning::{script} terminó con error ({codigo}); se mantienen sus datos anteriores.")
    rutas = [r for carpetas in FUENTES.values() for r in carpetas if (RAIZ / r).exists()]
    LISTA_RUTAS.write_text("\n".join(rutas) + "\n")
    print(f"\nFuentes solo repo: {len(FUENTES) - len(fallas)} de {len(FUENTES)} sin errores.")


if __name__ == "__main__":
    main()
