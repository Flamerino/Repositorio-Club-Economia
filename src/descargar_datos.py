"""Descarga los datos crudos desde el Drive del Club a data/raw/.

Uso:
    python src/descargar_datos.py                 # todo
    python src/descargar_datos.py --max-mb 50     # saltea archivos pesados
    python src/descargar_datos.py --institucion BCRA

Requiere que la carpeta de Drive esté compartida como
"Cualquier persona con el enlace puede ver".
"""
import argparse
import csv
from pathlib import Path

import gdown

RAIZ = Path(__file__).resolve().parents[1]
CATALOGO = RAIZ / "data" / "catalogo_fuentes.csv"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--max-mb", type=float, default=None, help="Tamaño máximo por archivo (MB)")
    p.add_argument("--institucion", default=None, help="INDEC, BCRA, MECON, OPC, Banco Mundial")
    p.add_argument("--forzar", action="store_true", help="Volver a bajar aunque ya exista")
    args = p.parse_args()

    with open(CATALOGO, encoding="utf-8") as f:
        filas = list(csv.DictReader(f))

    for fila in filas:
        if args.institucion and fila["institucion"].lower() != args.institucion.lower():
            continue
        if args.max_mb and float(fila["tamano_mb"]) > args.max_mb:
            print(f"[salteado] {fila['archivo']} ({fila['tamano_mb']} MB)")
            continue

        destino = RAIZ / fila["ruta_destino"] / fila["archivo"]
        if destino.exists() and not args.forzar:
            print(f"[ya existe] {destino.relative_to(RAIZ)}")
            continue

        destino.parent.mkdir(parents=True, exist_ok=True)
        print(f"[bajando] {fila['archivo']}")
        gdown.download(id=fila["drive_id"], output=str(destino), quiet=True)


if __name__ == "__main__":
    main()
