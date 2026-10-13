"""Escribe data/estado_actualizacion.json con la última fecha de cada fuente en la base.

Lo commitea GitHub Actions después de cada corrida: deja registro de qué se actualizó y
mantiene el repo activo (GitHub pausa los workflows programados tras 60 días sin cambios).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from supabase_db import ultima_fecha  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
SERIES = {
    "BCRA por API (reservas, base, depósitos, tasas...)": "bcra_api_74",
    "BCRA ITCRM": "bcra_itcrm",
    "INDEC IPC nivel general": "indec_ipc_nivel_general",
    "Elaboración propia (diarias)": "club_respaldo_base",
    "Elaboración propia (con IPC)": "club_base_real",
    "Pobreza (EPH, semestral)": "club_pobreza",
    "Canasta Básica Total (INDEC)": "indec_cbt_gran_buenos_aires",
}

estado = {"corrida": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
          "ultimo_dato": {k: ultima_fecha(v) for k, v in SERIES.items()}}
(RAIZ / "data" / "estado_actualizacion.json").write_text(json.dumps(estado, indent=2, ensure_ascii=False) + "\n")
print(json.dumps(estado, indent=2, ensure_ascii=False))
