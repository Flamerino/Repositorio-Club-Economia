"""Actualiza todas las fuentes que se guardan solo en el repo (no en la base ni en la página).

Lo corre GitHub Actions todos los lunes. Cada fuente es independiente: si una falla, deja un
aviso y sigue con las demás. Después el workflow commitea data/processed/.

PARA SUMAR UNA FUENTE NUEVA:
  1. Crear src/<fuente>/actualizar.py que escriba data/processed/<fuente>/series.csv y
     observaciones.csv (mismas columnas que el resto) y valide los datos antes de guardar.
  2. Crear data/processed/<fuente>/.solo_repo (mientras no se quiera mostrar en la página).
  3. Agregar la ruta del script a FUENTES, abajo. No hace falta tocar el workflow.

Uso: python src/actualizar_solo_repo.py
"""
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FUENTES = [
    "src/datos_gob/actualizar.py",      # INDEC, Trabajo, ANSES, Hacienda vía datos.gob.ar
    "src/mercados/actualizar.py",       # dólares, brechas y riesgo país (ArgentinaDatos)
    "src/banco_mundial/actualizar.py",  # comparación con la región
]


def main():
    fallas = []
    for script in FUENTES:
        print(f"\n===== {script}", flush=True)
        try:
            r = subprocess.run([sys.executable, str(RAIZ / script)], cwd=RAIZ, timeout=15 * 60)
            codigo = r.returncode
        except subprocess.TimeoutExpired:
            codigo = "tiempo agotado (15 min)"
        if codigo != 0:
            fallas.append(script)
            print(f"::warning::{script} terminó con error ({codigo}); se mantienen sus datos anteriores.")
    print(f"\nFuentes solo repo: {len(FUENTES) - len(fallas)} de {len(FUENTES)} sin errores.")


if __name__ == "__main__":
    main()
