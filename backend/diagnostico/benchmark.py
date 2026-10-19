"""Local, read-only CNN benchmark: python -m diagnostico.benchmark --image PATH."""
import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--image', type=Path)
    parser.add_argument('--sizes', default='224,512')
    parser.add_argument('--threads', default='4')
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    import numpy as np
    import torch
    import torchvision.transforms as T
    import torchxrayvision as xrv
    from PIL import Image
    from .services import DetectorTorax
    from .gradcam import GeneradorGradCAM

    # No clinical identifiers or images are written to the benchmark output.
    path = args.image or next(Path('media').rglob('*.jpg'), None)
    if not path:
        parser.error('Provide --image with an existing radiograph.')
    if path.suffix.lower() in {'.dcm', '.dicom'}:
        from estudios.utils import dicom_display_pixels, leer_dicom
        ds = leer_dicom(path)
        array, maxval = dicom_display_pixels(ds).astype(np.float32), 255.0
    else:
        with Image.open(path) as image:
            array, maxval = np.array(image.convert('L'), dtype=np.float32), 255.0
    model = DetectorTorax.cargar()
    for threads in map(int, args.threads.split(',')):
        torch.set_num_threads(threads)
        for size in map(int, args.sizes.split(',')):
            DetectorTorax._input_size = size
            DetectorTorax._transform = T.Compose([xrv.datasets.XRayCenterCrop(), xrv.datasets.XRayResizer(size)])
            times = []
            for _ in range(3):
                start = time.perf_counter()
                result = DetectorTorax.predecir(array, maxval)
                times.append(round(time.perf_counter() - start, 4))
            tensor = DetectorTorax._preprocesar(array, maxval)
            cams = []
            for index in (0, 1, 0):
                start = time.perf_counter()
                cam = GeneradorGradCAM.calcular(model, tensor, index)
                assert np.isfinite(cam).all()
                cams.append(round(time.perf_counter() - start, 4))
            print(json.dumps({'size': size, 'threads': threads, 'prediction_seconds': times,
                              'gradcam_seconds': cams, 'scores': result['probabilidades']}, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    main()
