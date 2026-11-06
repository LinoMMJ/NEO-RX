"""Explore frozen-model operating points on VALIDATION only; never deploy them."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import time

import numpy as np


def dataset_identity(manifest_text, splits):
    rows = sorted((r['Image Index'], r['Patient ID'], r['Finding Labels'],
                   r.get('View Position', ''), r['sha256'])
                  for r in csv.DictReader(io.StringIO(manifest_text)))
    return hashlib.sha256(json.dumps([rows, splits], sort_keys=True).encode()).hexdigest()


def operating_points(target, scores):
    """Exact >= thresholds, grouping tied scores; no rounded-threshold decisions."""
    target, scores = np.asarray(target), np.asarray(scores)
    if target.ndim != 1 or target.shape != scores.shape or len(target) == 0:
        raise ValueError('Invalid prediction dimensions')
    if not np.isin(target, [0, 1]).all() or not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
        raise ValueError('Invalid binary targets or sigmoid scores')
    positives, negatives = int(target.sum()), int((1 - target).sum())
    if not positives or not negatives:
        raise ValueError('Both positive and negative validation examples are required')
    order = np.argsort(-scores, kind='stable')
    sorted_scores, sorted_targets = scores[order], target[order]
    ends = np.r_[np.flatnonzero(np.diff(sorted_scores) != 0), len(scores) - 1]
    tp = np.cumsum(sorted_targets)[ends].astype(int)
    fp = ends + 1 - tp
    return [dict(threshold=float(sorted_scores[end]), tp=int(t), fp=int(f),
                 fn=positives-int(t), tn=negatives-int(f),
                 sensitivity=float(t/positives), specificity=float(1-f/negatives),
                 precision=float(t/(t+f)), false_positives_per_1000_negatives=float(1000*f/negatives))
            for end, t, f in zip(ends, tp, fp)]


def exploratory_candidates(points, targets=(0.80, 0.85, 0.90, 0.95)):
    # Descending thresholds: first eligible point minimizes emitted positives.
    return [dict(sensitivity_target=goal, **next(p for p in points if p['sensitivity'] >= goal),
                 enabled=False, status='exploratory_validation_only') for goal in targets]


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def prepare_validation(bundle, previous, output, data_root, expected_checkpoint, expected_data):
    import pandas as pd
    import yaml
    from training.analyze_targets import analyze
    from training.configuration import get_target_labels
    from training.kaggle_run import verify_bundle
    from training.model import load_checkpoint
    from training.validate_dataset import index_images

    build = verify_bundle(bundle)
    if json.loads((previous / 'source_bundle.json').read_text(encoding='utf-8')) != build:
        raise ValueError('Use the original training code bundle')
    cfg = yaml.safe_load((previous / 'config.runtime.yaml').read_text(encoding='utf-8'))
    checkpoint = previous / 'checkpoints/best.pt'
    if not checkpoint.exists():
        checkpoint = previous / 'checkpoints' / cfg['model']['checkpoint_name']
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != expected_checkpoint:
        raise ValueError('Checkpoint differs from the already reviewed frozen model')
    manifest_text = (previous / 'manifests/clean_manifest.csv').read_text(encoding='utf-8-sig')
    splits = json.loads((previous / 'manifests/splits.json').read_text(encoding='utf-8'))
    if dataset_identity(manifest_text, splits) != expected_data:
        raise ValueError('Dataset identity differs: labels, patients, hashes or splits changed')
    analyze(manifest_text, splits)  # Metadata overlap checks, no TEST inference.
    best = load_checkpoint(checkpoint)
    labels = get_target_labels(cfg)
    if best['pathologies'] != labels:
        raise ValueError('Checkpoint label order differs from configuration')
    rows = {r['Image Index']: r for r in csv.DictReader(io.StringIO(manifest_text))}
    paths = index_images(data_root)
    val_rows = []
    for index, name in enumerate(splits['val'], 1):
        row = dict(rows[name])
        matches = paths.get(name, [])
        if len(matches) != 1:
            raise ValueError(f'Missing or ambiguous VALIDATION image: {name}')
        path = matches[0]
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError(f'VALIDATION image changed: {name}')
        row['image_path'] = str(path)
        val_rows.append(row)
        if index % 1000 == 0 or index == len(splits['val']):
            print(f'VALIDATION verified: {index:,}/{len(splits["val"]):,}', flush=True)
    provenance = dict(partition='val', samples=len(val_rows), checkpoint_sha256=expected_checkpoint,
                      dataset_identity=expected_data, original_thresholds=best['thresholds'],
                      original_decision_policy=best['decision_policy'],
                      selected_epoch_zero_based=best['extra']['epoch'],
                      validation_metrics_at_training=best.get('metrics', {}),
                      test_inference_performed=False, deployment_enabled=False)
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    return cfg, checkpoint, pd.DataFrame(val_rows), labels, best['thresholds']


class ValidationProgress:
    def __init__(self, loader):
        self.loader = loader

    def __iter__(self):
        started = last = time.monotonic()
        completed, total = 0, len(self.loader.dataset)
        for batch in self.loader:
            yield batch
            completed += len(batch[2])
            now = time.monotonic()
            if completed == len(batch[2]) or now-last >= 30 or completed == total:
                rate = completed / max(now-started, 1e-6)
                print(f'VALIDATION inference: {completed:,}/{total:,} | {rate:.1f} images/s | '
                      f'ETA inference only: {(total-completed)/rate/60:.1f} min', flush=True)
                last = now


def run(args):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import torch
    from sklearn.metrics import average_precision_score, roc_auc_score
    from torch.utils.data import DataLoader
    from training.dataset import NIHDataset, build_eval_transform
    from training.evaluate import evaluate_model, compute_metrics
    from training.model import load_finetuned_model
    from training.kaggle_run import discover_data_root

    if not torch.cuda.is_available():
        raise RuntimeError('GPU required for this notebook; enable it before running')
    root = args.data_root or discover_data_root(Path('/kaggle/input'))
    cfg, checkpoint, frame, labels, original = prepare_validation(
        args.bundle, args.previous, args.output, root, args.expected_checkpoint, args.expected_data)
    model = load_finetuned_model(checkpoint, base_weights=cfg['model']['base_weights'],
                                cache_dir=str(args.bundle / 'weights')).to('cuda')
    ds = NIHDataset(frame, labels, build_eval_transform())
    loader = DataLoader(ds, batch_size=16, num_workers=2, shuffle=False, drop_last=False, pin_memory=True)
    y, scores, ids = evaluate_model(model, ValidationProgress(loader), torch.device('cuda'))
    if ids != frame['Image Index'].tolist() or len(ids) != len(ds):
        raise ValueError('Validation inference lost or reordered samples')
    # Store scores once; later exploration does not need another GPU run.
    np.savez_compressed(args.output / 'validation_predictions.npz', targets=y, probabilities=scores,
                        image_ids=np.asarray(ids), labels=np.asarray(labels))
    write_csv(args.output / 'validation_predictions.csv', [dict(image_id=name, **{
        f'{label}_{kind}': float(array[i, j]) for j, label in enumerate(labels)
        for kind, array in [('target', y), ('score', scores)]}) for i, name in enumerate(ids)])
    candidates, baseline, discrimination = [], [], []
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for j, label in enumerate(labels):
        points = operating_points(y[:, j], scores[:, j])
        write_csv(args.output / f'thresholds_{label}.csv', points)
        candidates.extend(dict(label=label, **p) for p in exploratory_candidates(points))
        m = compute_metrics(y[:, j], scores[:, j], original[label])
        tn, fp, fn, tp = np.asarray(m['confusion_matrix']).ravel().tolist()
        baseline.append(dict(label=label, threshold=original[label], sensitivity=m['sensitivity'],
                             precision=m['precision'] if tp+fp else None, tp=tp, fp=fp, fn=fn, tn=tn,
                             note='raw_threshold_only_not_deployed_routing'))
        discrimination.append(dict(label=label, auc=float(roc_auc_score(y[:, j], scores[:, j])),
                                   average_precision=float(average_precision_score(y[:, j], scores[:, j]))))
        axes[0].plot([p['sensitivity'] for p in points], [p['precision'] for p in points], label=label)
        axes[1].plot([p['sensitivity'] for p in points], [p['false_positives_per_1000_negatives'] for p in points], label=label)
    write_csv(args.output / 'comparacion_sensibilidad.csv', candidates)
    write_csv(args.output / 'umbrales_originales_VALIDACION.csv', baseline)
    write_csv(args.output / 'discriminacion_VALIDACION.csv', discrimination)
    for ax, title, ylabel in zip(axes, ['VALIDACION: sensibilidad y precision', 'VALIDACION: costo en falsas alarmas'],
                                  ['Precision (valor predictivo positivo)', 'Falsos positivos / 1000 negativos']):
        ax.set(xlabel='Sensibilidad', ylabel=ylabel, title=title, xlim=(0, 1))
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(args.output / 'sensibilidad_falsas_alarmas.png', dpi=160)
    plt.close(fig)
    (args.output / 'LEEME.txt').write_text(
        'Analisis exploratorio de VALIDACION, no evaluacion independiente ni autorizacion clinica.\n'
        '80/85/90/95% son escenarios para comparar, no criterios clinicos aprobados.\n'
        'Los umbrales originales y el checkpoint no se modificaron; ninguna clase se habilito.\n'
        'Una mayor sensibilidad puede implicar muchas falsas alarmas y menor precision.\n'
        'Los scores sigmoid no estan demostrados como probabilidades clinicas calibradas.\n'
        'Las categorias usan etiquetas derivadas NIH, no etiologias confirmadas.\n'
        'Cada fila es una clase binaria; no mide el enrutamiento conjunto del sistema.\n'
        'TEST ya fue consultado: una politica revisada necesita evaluacion independiente.\n'
        'Esta validacion se uso tambien para seleccionar el modelo: no demuestra generalizacion.\n', encoding='utf-8')
    print('\nVALIDATION exploration completed. No model or deployment policy changed.', flush=True)


def main():
    parser = argparse.ArgumentParser()
    for name in ('bundle', 'previous', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--data-root', type=Path)
    parser.add_argument('--expected-checkpoint', required=True)
    parser.add_argument('--expected-data', required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    status = args.output / 'STATUS.json'
    status.write_text(json.dumps(dict(status='running', partition='val')), encoding='utf-8')
    try:
        run(args)
    except Exception as error:
        status.write_text(json.dumps(dict(status='failed', error=str(error))), encoding='utf-8')
        raise
    status.write_text(json.dumps(dict(status='validation_analysis_complete', partition='val',
                                     deployment_enabled=False)), encoding='utf-8')


if __name__ == '__main__':
    main()
