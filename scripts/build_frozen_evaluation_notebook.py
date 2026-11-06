"""Create a separate evaluator without changing the user's running bundle."""
import json
import argparse
from pathlib import Path
from build_kaggle_bundle import cell, notebook

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--cpu', action='store_true', help='Create a separate CPU-only notebook')
options = parser.parse_args()
script = (ROOT / 'backend/training/evaluate_frozen.py').read_text(encoding='utf-8')
cells = [cell('markdown', '''# NeoRX · Cierre por tiempo y evaluación del mejor modelo
Utiliza este notebook **cuando termine la cuarta sesión** y hayas guardado su salida.
Adjunta el paquete ORIGINAL `neorx_kaggle_entrenamiento`, NIH completo y el avance más reciente.
No vuelvas a subir ni cambies el ZIP de código. Esta evaluación conserva los pesos y umbrales de `best.pt`.
El cierre por presupuesto queda registrado sin afirmar que se completaron las 21 épocas.
Activa GPU e Internet y usa **Save Version → Save & Run All**.
Después de consultar TEST, no lo uses para decidir otras épocas, modelos o umbrales: necesitarías otro conjunto independiente.
'''), cell('code', '''# Completa con la ruta REAL del avance guardado al terminar la cuarta sesión.
PREVIOUS_OUTPUT = ""  # /kaggle/input/.../neorx-run
DATA_ROOT = ""        # detectar automáticamente la entrada NIH
CLOSE_BY_BUDGET = True  # cierre definitivo de este experimento por tiempo disponible
'''), notebook()['cells'][2], cell('code', f'''# Evaluador independiente; no modifica el paquete original.
script_path = WORK / 'evaluate_frozen.py'
script_path.write_text({script!r}, encoding='utf-8')
if not PREVIOUS_OUTPUT:
    raise RuntimeError('Copia la ruta neorx-run de la salida de la cuarta sesión en PREVIOUS_OUTPUT.')
OUTPUT = WORK / 'neorx-evaluation'
args = [sys.executable, '-u', str(script_path), '--bundle', str(BUNDLE),
        '--previous-output', PREVIOUS_OUTPUT, '--output', str(OUTPUT)]
if DATA_ROOT:
    args += ['--data-root', DATA_ROOT]
if CLOSE_BY_BUDGET:
    args += ['--close-by-budget']
log_path = WORK / 'evaluation_console.log'
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
    raise RuntimeError('Evaluación incompleta: revisa el log y STATUS.json.')
'''), cell('code', '''from IPython.display import display, FileLink
print((OUTPUT / 'STATUS.json').read_text(encoding='utf-8'))
print('Descarga el ZIP y revisa evaluation/metrics.csv, evaluation/routing_summary.json y FREEZE.json.')
print('Una evaluación correcta del software no garantiza resultados clínicos adecuados.')
display(FileLink('/kaggle/working/neorx_entrenamiento_resultados.zip'))
''')]
book = notebook()
if options.cpu:
    intro = ''.join(cells[0]['source']).replace(
        '# NeoRX · Cierre por tiempo y evaluación del mejor modelo',
        '# NeoRX · Evaluación completa con CPU de Kaggle (sin cuota GPU)'
    ).replace('Activa GPU e Internet y usa **Save Version → Save & Run All**.',
              'Selecciona **Accelerator: None / CPU**, activa Internet y usa **Save Version → Save & Run All**. '
              'Se evalúa todo TEST con el mismo modelo, resolución y umbrales. '
              'CPU puede tardar varias horas o superar el límite de sesión: no hay duración garantizada. '
              'El log estima el tiempo restante de inferencia una vez que empieza a procesar imágenes.')
    cells[0] = cell('markdown', intro)
    config = ''.join(cells[1]['source']).replace('PREVIOUS_OUTPUT = ""',
        'PREVIOUS_OUTPUT = "/kaggle/input/datasets/javier64/neorx-avance-4/neorx-run"')
    cells[1] = cell('code', config)
    bootstrap = ''.join(cells[2]['source'])
    guard = "if not torch.cuda.is_available():\n    raise RuntimeError('Activa Accelerator: GPU y guarda una nueva versión con GPU.')\nprint('GPU:', torch.cuda.get_device_name(0), '| PyTorch:', torch.__version__)"
    assert guard in bootstrap, 'Original bootstrap changed; review CPU generation'
    bootstrap = bootstrap.replace(guard,
        "print('Evaluación en CPU de Kaggle | PyTorch:', torch.__version__)\n"
        "os.environ['OMP_NUM_THREADS'] = '2'\nos.environ['MKL_NUM_THREADS'] = '2'")
    cells[2] = cell('code', bootstrap)
    execution = ''.join(cells[3]['source']).replace(
        "'--previous-output', PREVIOUS_OUTPUT, '--output', str(OUTPUT)]",
        "'--previous-output', PREVIOUS_OUTPUT, '--output', str(OUTPUT), '--device', 'cpu', '--cpu-threads', '2']")
    cells[3] = cell('code', execution)
book['cells'] = cells
for i, item in enumerate(cells):
    item['id'] = f'evaluation-{i:02d}'
    if item['cell_type'] == 'code':
        compile(''.join(item['source']), f'cell-{i}', 'exec')
targets = ([ROOT / 'entrega_kaggle/NeoRX_Evaluar_CPU.ipynb', ROOT / 'notebooks/neorx_evaluate_cpu.ipynb']
           if options.cpu else
           [ROOT / 'entrega_kaggle/NeoRX_Evaluar_Mejor_Avance.ipynb', ROOT / 'notebooks/neorx_evaluate_frozen.ipynb'])
for target in targets:
    target.write_text(json.dumps(book, indent=2, ensure_ascii=False), encoding='utf-8')
print('Created separate evaluation notebook; original training ZIP is unchanged.')
