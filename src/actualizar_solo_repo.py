"""Actualiza todas las fuentes que se guardan solo en el repo (no en la base ni en la página).

Lo corre GitHub Actions todos los lunes. Cada fuente es independiente: si una falla, deja un
aviso y sigue con las demás. Después el workflow commitea data/processed/.

PARA SUMAR UNA FUENTE NUEVA:
  1. Crear src/<fuente>/actualizar.py que escriba data/processed/<fuente>/series.csv y
     observaciones.csv (mismas columnas que el resto) y valide los datos antes de guardar.
  2. Crear data/processed/<fuente>/.solo_repo (mientras no se quiera mostrar en la página).
  3. Agregar el script a FUENTES, abajo, con las carpetas que escribe (las de data/raw/ con un
     archivo por serie, para abrir directo en Excel). No hace falta tocar el workflow.

Uso: python src/actualizar_solo_repo.py
"""
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FUENTES = {  # script: carpetas que escribe (el workflow commitea esas carpetas)
    "src/datos_gob/actualizar.py": ["data/processed/datos_gob", "data/raw/datos_gob", "data/raw/indec/salarios"],
    "src/mercados/actualizar.py": ["data/processed/mercados", "data/raw/mercados"],
    "src/banco_mundial/actualizar.py": ["data/processed/banco_mundial", "data/raw/banco_mundial/indicadores"],
    "src/internacional/actualizar.py": ["data/processed/internacional", "data/raw/internacional", "data/raw/maddison"],
    "src/opinion/actualizar.py": ["data/processed/opinion"],
    "src/bcra/balance_cambiario.py": ["data/processed/balance_cambiario"],
    "src/bcra/rem.py": ["data/processed/rem"],
    "src/indec/distribucion.py": ["data/processed/distribucion"],
}
LISTA_RUTAS = RAIZ / ".rutas_solo_repo"  # la lee el workflow para saber qué commitear


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
    rutas = [r for carpetas in FUENTES.values() for r in carpetas if (RAIZ / r).exists()]
    LISTA_RUTAS.write_text("\n".join(rutas) + "\n")
    print(f"\nFuentes solo repo: {len(FUENTES) - len(fallas)} de {len(FUENTES)} sin errores.")


if __name__ == "__main__":
    main()
