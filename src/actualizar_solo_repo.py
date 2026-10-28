"""Actualiza las fuentes complementarias (todas salvo BCRA, IPC, pobreza y series propias, que
tienen su propio paso en el workflow).

Lo corre GitHub Actions todos los lunes. Cada fuente es independiente: si una falla, deja un aviso
y sigue con las demás. Las que figuran en SOLO_REPO (src/almacen.py) se publican solo en datos/;
las demás se suben además a la base, así aparecen en la página (pestaña "Explorar series").

PARA SUMAR UNA FUENTE NUEVA:
  1. Crear src/<fuente>/actualizar.py que escriba data/processed/<fuente>/series.csv y
     observaciones.csv (área de trabajo de la corrida) y valide los datos antes de guardar.
  2. Agregarla a FUENTES, abajo, con su carpeta y las carpetas de data/raw/ que escribe.
  3. Si todavía no se quiere mostrar en la página, agregar la carpeta a SOLO_REPO en src/almacen.py.
No hace falta tocar el workflow.

Uso: python src/actualizar_solo_repo.py
"""
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from almacen import PROCESSED, SOLO_REPO  # noqa: E402

FUENTES = {  # script: (carpeta en data/processed/, carpetas de data/raw/ que escribe y se versionan)
    "src/datos_gob/actualizar.py": ("datos_gob", ["data/raw/datos_gob", "data/raw/indec/salarios"]),
    "src/mercados/actualizar.py": ("mercados", ["data/raw/mercados"]),
    "src/banco_mundial/actualizar.py": ("banco_mundial", ["data/raw/banco_mundial/indicadores"]),
    "src/internacional/actualizar.py": ("internacional", ["data/raw/internacional", "data/raw/maddison"]),
    "src/opinion/actualizar.py": ("opinion", []),
    "src/bcra/balance_cambiario.py": ("balance_cambiario", []),
    "src/bcra/rem.py": ("rem", []),
    "src/indec/distribucion.py": ("distribucion", []),
}
LISTA_RUTAS = RAIZ / ".rutas_solo_repo"  # la lee el workflow para saber qué commitear


def main():
    fallas = []
    for script, (carpeta, _) in FUENTES.items():
        print(f"\n===== {script}", flush=True)
        try:
            codigo = subprocess.run([sys.executable, str(RAIZ / script)], cwd=RAIZ, timeout=8 * 60).returncode
        except subprocess.TimeoutExpired:
            codigo = "tiempo agotado (8 min)"
        if codigo != 0:
            fallas.append(script)
            print(f"::warning::{script} terminó con error ({codigo}); se mantienen sus datos anteriores.")

    # las fuentes que no están en SOLO_REPO se suben a la base (aparecen en la página)
    a_la_base = [c for s, (c, _) in FUENTES.items()
                 if c not in SOLO_REPO and s not in fallas and (PROCESSED / c / "series.csv").exists()]
    if a_la_base and os.environ.get("SUPABASE_URL"):
        print(f"\n===== Subiendo a la base: {', '.join(a_la_base)}", flush=True)
        subprocess.run([sys.executable, str(RAIZ / "src" / "cargar_supabase.py"), *a_la_base], cwd=RAIZ)

    rutas = [r for _, carpetas in FUENTES.values() for r in carpetas if (RAIZ / r).exists()]
    LISTA_RUTAS.write_text("\n".join(rutas) + "\n")
    print(f"\nFuentes complementarias: {len(FUENTES) - len(fallas)} de {len(FUENTES)} sin errores.")


if __name__ == "__main__":
    main()
