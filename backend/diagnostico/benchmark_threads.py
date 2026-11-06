"""Read-only CPU benchmark with synthetic pixels and fresh request threads."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv


def main():
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    import numpy as np
    import torch
    from .services import DetectorTorax

    image = np.linspace(0, 255, 512 * 512, dtype=np.float32).reshape(512, 512)
    DetectorTorax.cargar()

    def predict():
        start = time.perf_counter()
        result = DetectorTorax.predecir(image, 255)
        return {'seconds': round(time.perf_counter() - start, 3),
                'threads': torch.get_num_threads(), 'scores': result['probabilidades']}

    print(json.dumps({'main': predict()}), flush=True)
    for index in range(2):
        with ThreadPoolExecutor(max_workers=1) as worker:
            print(json.dumps({'request': index, **worker.submit(predict).result()}), flush=True)


if __name__ == '__main__':
    main()
