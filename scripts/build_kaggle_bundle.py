"""Build an allowlisted training handoff, excluding .env, DB, media and Git."""
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'entrega_kaggle'
MODULES = ['__init__.py', 'acceptance.py', 'analyze_targets.py', 'configuration.py', 'create_splits.py',
           'dataset.py', 'evaluate.py', 'kaggle_run.py', 'model.py', 'session.py',
           'threshold_optimizer.py', 'train.py', 'validate_dataset.py',
           'config.priority2.v2.kaggle.yaml', 'requirements.kaggle.txt']
WEIGHTS = 'pc-nih-rsna-siim-vin-resnet50-test512-e400-state.pt'


def cell(kind, text):
    value = {'cell_type': kind, 'metadata': {}, 'source': text.strip().splitlines(keepends=True)}
    if kind == 'code':
        value.update(execution_count=None, outputs=[])
    return value


def notebook():
    cells = [cell('markdown', '''# NeoRX v2 · Derrame pleural y cuatro categorías equilibradas
Entrenamiento nocturno reanudable de ResNet-50 (512 × 512). Modelo experimental.
Agrega el dataset NIH completo y el paquete `neorx_kaggle_entrenamiento.zip` como una entrada privada.
Activa **GPU** e **Internet**. Ejecuta mediante **Save Version → Save & Run All**.
Consulta `GUIA_KAGGLE.md`: primero TRAIN, luego EVALUATE en otra versión. No se promete precisión ni duración.
'''), cell('code', '''# Única celda que necesitas editar.
MODE = "train"                 # "train" o "evaluate"
DATA_ROOT = ""                 # vacío: detectar Data_Entry_2017.csv; si falla, ruta de la carpeta NIH
PREVIOUS_OUTPUT = ""           # para reanudar/evaluar: /kaggle/input/.../neorx-run
SESSION_HOURS = 8              # reduce si tu cuota/límite disponible es menor
RESERVE_MINUTES = 45           # margen para guardar; no equivale al límite oficial de Kaggle
BATCH_SIZE = 16                # si hay falta de memoria, inicia un experimento nuevo con 8
WORKERS = 2                    # no utiliza automáticamente las dos GPU de T4 x2
'''), cell('code', '''from pathlib import Path
import json, os, sys, zipfile, subprocess, shutil

INPUT = Path('/kaggle/input')
WORK = Path('/kaggle/working')
WORK.mkdir(exist_ok=True)
bundles = list(INPUT.rglob('bundle_manifest.json'))
if not bundles:
    archives = list(INPUT.rglob('neorx_kaggle_entrenamiento.zip'))
    if len(archives) != 1:
        raise RuntimeError('Agrega el paquete de código como Dataset privado; debe haber una sola copia.')
    target = WORK / 'neorx-code'
    target.mkdir(exist_ok=True)
    with zipfile.ZipFile(archives[0]) as z:
        for member in z.infolist():
            resolved = (target / member.filename).resolve()
            if not resolved.is_relative_to(target.resolve()) or (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise RuntimeError('Ruta no permitida en el ZIP')
        z.extractall(target)
    bundles = list(target.rglob('bundle_manifest.json'))
if len(bundles) != 1:
    raise RuntimeError('Hay varios paquetes de código. Deja solo la versión que vas a utilizar.')
BUNDLE = bundles[0].parent
print('Código:', BUNDLE)
print('Entradas NIH:', [str(p.parent) for p in INPUT.rglob('Data_Entry_2017.csv')])
print('Salidas anteriores:', [str(p.parent) for p in INPUT.rglob('STATUS.json')])
# PyTorch/CUDA se conservan tal como los proporciona Kaggle.
subprocess.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
                '-r', str(BUNDLE / 'training/requirements.kaggle.txt')], check=True)
sys.path.insert(0, str(BUNDLE))
os.environ['PYTHONPATH'] = str(BUNDLE)
os.environ['PYTHONUNBUFFERED'] = '1'
from training.kaggle_run import verify_bundle
info = verify_bundle(BUNDLE)
import torch
if not torch.cuda.is_available():
    raise RuntimeError('Activa Accelerator: GPU y guarda una nueva versión con GPU.')
print('GPU:', torch.cuda.get_device_name(0), '| PyTorch:', torch.__version__)
print('Imágenes de referencia:', info['reference_images'])
'''), cell('code', '''OUTPUT = WORK / 'neorx-run'
args = [sys.executable, '-u', '-m', 'training.kaggle_run', '--bundle', str(BUNDLE),
        '--output', str(OUTPUT), '--mode', MODE, '--session-hours', str(SESSION_HOURS),
        '--reserve-minutes', str(RESERVE_MINUTES), '--batch-size', str(BATCH_SIZE), '--workers', str(WORKERS)]
if DATA_ROOT:
    args += ['--data-root', DATA_ROOT]
if PREVIOUS_OUTPUT:
    args += ['--previous-output', PREVIOUS_OUTPUT]
log_path = WORK / 'neorx_console.log'
with log_path.open('w', encoding='utf-8') as log:
    process = subprocess.Popen(args, cwd=BUNDLE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, bufsize=1)
    for line in process.stdout:
        print(line, end='', flush=True)
        log.write(line)
        log.flush()
    return_code = process.wait()
if OUTPUT.exists():
    shutil.copy2(log_path, OUTPUT / 'console.log')
    from training.kaggle_run import package_outputs
    package_outputs(OUTPUT)
if return_code:
    raise RuntimeError('La ejecución se detuvo por un error. Revisa neorx_console.log y STATUS.json; no es un entrenamiento completado.')
'''), cell('code', '''from IPython.display import display, FileLink
status = json.loads((OUTPUT / 'STATUS.json').read_text(encoding='utf-8'))
print(json.dumps(status, indent=2, ensure_ascii=False))
if status['status'] == 'paused_time_budget':
    print('AVANCE GUARDADO. Agrega la salida de esta versión como entrada y rellena PREVIOUS_OUTPUT para continuar.')
elif status['status'] in ('completed', 'early_stopped'):
    print('ENTRENAMIENTO TERMINADO. La siguiente versión debe usar MODE="evaluate" y PREVIOUS_OUTPUT.')
elif status['status'] == 'evaluated':
    print('EVALUACIÓN TERMINADA. Revisa métricas y routing_summary.json antes de incorporar el checkpoint.')
display(FileLink('/kaggle/working/neorx_entrenamiento_resultados.zip'))
''')]
    return {'cells': cells, 'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                                       'language_info': {'name': 'python'}}, 'nbformat': 4, 'nbformat_minor': 5}


def main():
    DEST.mkdir(exist_ok=True)
    files = {f'training/{name}': (ROOT / 'backend/training' / name).read_bytes() for name in MODULES}
    files['diagnostico/__init__.py'] = b''
    files['diagnostico/priority_policy.py'] = (ROOT / 'backend/diagnostico/priority_policy.py').read_bytes()
    files[f'weights/{WEIGHTS}'] = (ROOT / 'backend/models' / WEIGHTS).read_bytes()
    with zipfile.ZipFile(ROOT / 'results.zip') as archive:
        manifests = [name for name in archive.namelist() if name.endswith('/clean_manifest.csv')]
        if len(manifests) != 1:
            raise ValueError('Expected a single reference manifest')
        name = manifests[0]
        rows = list(csv.DictReader(io.StringIO(archive.read(name).decode('utf-8-sig'))))
        buffer = io.StringIO(newline='')
        columns = ['Image Index', 'Finding Labels', 'Patient ID', 'View Position']
        writer = csv.DictWriter(buffer, fieldnames=columns)
        writer.writeheader()
        writer.writerows({key: row.get(key, '') for key in columns} for row in rows)
        files['reference/metadata.csv'] = buffer.getvalue().encode('utf-8')
        files['reference/splits.json'] = archive.read(name.rsplit('/', 1)[0] + '/splits.json')
    guide = ROOT / 'docs/GUIA_KAGGLE_NOCTURNO.md'
    files['GUIA_KAGGLE.md'] = guide.read_bytes()
    manifest = {'format': 'neorx-kaggle-v1', 'reference_images': len(rows),
                'sha256': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}}
    files['bundle_manifest.json'] = json.dumps(manifest, indent=2).encode('utf-8')
    target = DEST / 'neorx_kaggle_entrenamiento.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=4) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    book = notebook()
    for i, item in enumerate(book['cells']):
        item['id'] = f'neorx-{i:02d}'
        if item['cell_type'] == 'code':
            compile(''.join(item['source']), f'cell-{i}', 'exec')
    destination = DEST / 'NeoRX_Entrenamiento_Nocturno.ipynb'
    destination.write_text(json.dumps(book, indent=2, ensure_ascii=False), encoding='utf-8')
    shutil.copy2(destination, ROOT / 'notebooks/neorx_training_kaggle_priority.ipynb')
    shutil.copy2(guide, DEST / 'GUIA_KAGGLE.md')
    checksums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (target, destination, DEST / 'GUIA_KAGGLE.md')}
    (DEST / 'SHA256.json').write_text(json.dumps(checksums, indent=2), encoding='utf-8')
    print(json.dumps({'folder': str(DEST), 'zip_MB': round(target.stat().st_size / 1e6, 1), 'files': len(files),
                      'reference_images': len(rows), 'notebook_cells': len(book['cells'])}, indent=2))


if __name__ == '__main__':
    main()
