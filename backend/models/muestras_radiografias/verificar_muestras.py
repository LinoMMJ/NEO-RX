"""Run the deployed NeoRX model over the curated public demo samples."""
import json
from pathlib import Path

from diagnostico.services import DetectorTorax


root = Path("/app/diagnostico/models/muestras_radiografias")
rows = []
for path in sorted(root.glob("*.png")):
    result = DetectorTorax.desde_png(str(path))
    row = {
        "archivo": path.name,
        "modelo": result.get("modelo"),
        "decision": result.get("decision"),
        "categoria": result.get("categoria"),
        "demostracion": result.get("demostracion"),
        "probabilidades": result.get("probabilidades"),
    }
    rows.append(row)
    print(path.name, "->", row["decision"].get("titulo"), flush=True)

print("RESULT_JSON=" + json.dumps(rows, ensure_ascii=False), flush=True)
