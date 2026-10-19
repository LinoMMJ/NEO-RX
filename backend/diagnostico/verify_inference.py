"""Compare the inference path with training evaluation on supplied local images.

No clinical labels are inferred from filenames. No database records are changed.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch
import torchxrayvision as xrv
from dotenv import load_dotenv
from PIL import Image


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('images', type=Path, nargs='+')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    from .services import DetectorTorax
    from training.dataset import build_eval_transform
    model = DetectorTorax.cargar()
    rows = []
    for path in args.images:
        with Image.open(path) as image:
            array = np.asarray(image.convert('L'), dtype=np.float32)
        trained_input = build_eval_transform()(xrv.datasets.normalize(array, 255.0)[None]).unsqueeze(0)
        runtime_input = DetectorTorax._preprocesar(array, 255.0)
        assert torch.equal(trained_input, runtime_input), 'Preprocessing differs from training'
        with torch.inference_mode():
            reference = torch.sigmoid(model.model(trained_input))[0].numpy()
        runs, scores = [], []
        for _ in range(2):
            start = time.perf_counter()
            result = DetectorTorax.predecir(array, 255.0)
            runs.append(time.perf_counter() - start)
            scores.append(np.array([result['probabilidades'][k] for k in model.pathologies]))
        delta = float(np.max(np.abs(reference - scores[0])))
        repeat_delta = float(np.max(np.abs(scores[0] - scores[1])))
        assert delta < 1e-5 and repeat_delta < 1e-6, 'Inference is inconsistent'
        row = {'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
               'dimensions': list(array.shape), 'seconds': runs,
               'training_path_max_difference': delta, 'repeat_max_difference': repeat_delta,
               'findings': result['hallazgos'], 'confirmed_diagnosis': None}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=True), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
