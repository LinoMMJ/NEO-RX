"""Build a separate VAL exploration notebook without rebuilding the training ZIP."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from build_kaggle_bundle import cell, notebook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from training.analyze_validation import dataset_identity


def main():
    with zipfile.ZipFile(ROOT / 'neorx_entrenamiento_resultados.zip') as archive:
        manifest = next(n for n in archive.namelist() if n.endswith('/manifests/clean_manifest.csv'))
        base = manifest.split('/manifests/')[0]
        splits = json.loads(archive.read(base + '/manifests/splits.json'))
        data_hash = dataset_identity(archive.read(manifest).decode('utf-8-sig'), splits)
        frozen = json.loads(archive.read(base + '/FREEZE.json'))
        checkpoint_name = next(n for n in archive.namelist() if n.endswith('.pt'))
        checkpoint_hash = hashlib.sha256(archive.read(checkpoint_name)).hexdigest()
        assert checkpoint_hash == frozen['checkpoint_sha256']
    script = (ROOT / 'backend/training/analyze_validation.py').read_text(encoding='utf-8')
    book = notebook()
    book['cells'] = [cell('markdown', '''# NeoRX · Análisis de sensibilidad en VALIDACIÓN
Usa el mismo modelo ya evaluado. **No entrena, no vuelve a inferir TEST y no habilita clases.**
Agrega como entradas privadas: **neorx_avance_4**, el paquete ORIGINAL
**neorx_kaggle_entrenamiento** y **NIH Chest X-rays completo**.
También admite la carpeta `neorx-evaluation` de la evaluación terminada en lugar del avance 4.
Deja solo una salida anterior adjunta. GPU T4 e Internet activados.
Ejecuta con **Save Version → Save & Run All**.
Los escenarios de sensibilidad 80/85/90/95% son exploratorios, no criterios clínicos aprobados.
Los resultados de TEST anteriores se conservan. Una política nueva necesita evaluación independiente.
'''), cell('code', '''# Puedes dejar ambos vacíos si adjuntas solo una salida anterior y un dataset NIH.
PREVIOUS_OUTPUT = ""  # carpeta neorx-run del avance 4, o neorx-evaluation
DATA_ROOT = ""        # carpeta que contiene el NIH completo; se detecta automáticamente
'''), notebook()['cells'][2], cell('code', f'''# Script independiente. Identidad del modelo y dataset revisados localmente.
script_path = WORK / 'analyze_validation.py'
script_path.write_text({script!r}, encoding='utf-8')
if not PREVIOUS_OUTPUT:
    previous_candidates = [p.parent for p in INPUT.rglob('source_bundle.json')
                           if (p.parent / 'manifests/splits.json').exists()
                           and (p.parent / 'checkpoints').is_dir()]
    if len(previous_candidates) != 1:
        raise RuntimeError('Deja solo el avance 4 o la evaluación como entrada, o escribe PREVIOUS_OUTPUT. '
                           + str(previous_candidates))
    PREVIOUS_OUTPUT = str(previous_candidates[0])
print('Salida anterior:', PREVIOUS_OUTPUT)
OUTPUT = WORK / 'neorx-validation-analysis'
if OUTPUT.exists():
    raise RuntimeError('Esta salida ya existe. Guarda/descarga sus resultados; para otra ejecución usa una sesión nueva.')
args = [sys.executable, '-u', str(script_path), '--bundle', str(BUNDLE),
        '--previous', PREVIOUS_OUTPUT, '--output', str(OUTPUT),
        '--expected-checkpoint', {checkpoint_hash!r}, '--expected-data', {data_hash!r}]
if DATA_ROOT:
    args += ['--data-root', DATA_ROOT]
log_path = WORK / 'validation_console.log'
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
    # Registrar conflictos, sin modificar paquetes ajenos para ocultarlos.
    for name, command in [('pip_check.txt', ['check']), ('pip_freeze.txt', ['freeze'])]:
        result = subprocess.run([sys.executable, '-m', 'pip', *command], capture_output=True, text=True)
        (OUTPUT / name).write_text(result.stdout + result.stderr, encoding='utf-8')
    with zipfile.ZipFile(WORK / 'neorx_validacion_sensibilidad.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(OUTPUT.rglob('*')):
            if path.is_file():
                z.write(path, 'neorx-validation-analysis/' + path.relative_to(OUTPUT).as_posix())
if return_code:
    raise RuntimeError('Análisis incompleto: revisa validation_console.log y STATUS.json.')
'''), cell('code', '''import pandas as pd
from IPython.display import display, FileLink, Image
print((OUTPUT / 'STATUS.json').read_text(encoding='utf-8'))
print('Resultados de VALIDACIÓN; no se habilitó ninguna clase ni se cambió el modelo.')
display(pd.read_csv(OUTPUT / 'comparacion_sensibilidad.csv'))
display(Image(filename=str(OUTPUT / 'sensibilidad_falsas_alarmas.png')))
display(FileLink('/kaggle/working/neorx_validacion_sensibilidad.zip'))
''')]
    for i, item in enumerate(book['cells']):
        item['id'] = f'validation-{i:02d}'
        if item['cell_type'] == 'code':
            compile(''.join(item['source']), f'cell-{i}', 'exec')
    for target in ('entrega_kaggle/NeoRX_Analizar_Sensibilidad_VALIDACION.ipynb',
                   'notebooks/neorx_analyze_validation.ipynb'):
        (ROOT / target).write_text(json.dumps(book, indent=2, ensure_ascii=False), encoding='utf-8')
    print('Created VAL-only notebook. Original training ZIP and TEST outputs unchanged.')


if __name__ == '__main__':
    main()
