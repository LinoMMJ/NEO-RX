"""Print an honest training-style summary from saved NeoRX validation scores."""
import argparse
import io
import json
from pathlib import Path
import zipfile

import numpy as np
from sklearn.metrics import f1_score


def summarize(targets, scores, thresholds):
    predictions = (scores >= thresholds).astype(int)
    sensitivities, precisions = [], []
    for index in range(targets.shape[1]):
        truth, predicted = targets[:, index].astype(bool), predictions[:, index].astype(bool)
        tp = int((truth & predicted).sum())
        sensitivities.append(tp / int(truth.sum()))
        emitted = int(predicted.sum())
        precisions.append(tp / emitted if emitted else 0.0)
    return {
        # Element-wise accuracy across five binary labels. It is not clinical efficacy.
        'binary_accuracy_micro': float((predictions == targets).mean()),
        # Every one of the five binary decisions must match for the image.
        'exact_match_all_5': float((predictions == targets).all(axis=1).mean()),
        'macro_sensitivity': float(np.mean(sensitivities)),
        'macro_precision': float(np.mean(precisions)),
        'macro_f1': float(f1_score(targets, predictions, average='macro', zero_division=0)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, default=Path('neorx_validacion_sensibilidad.zip'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    with zipfile.ZipFile(args.archive) as archive:
        raw = archive.read('neorx-validation-analysis/validation_predictions.npz')
    saved = np.load(io.BytesIO(raw), allow_pickle=False)
    targets, scores, labels = saved['targets'].astype(int), saved['probabilities'], saved['labels'].tolist()
    scenarios = {
        'threshold_0.50': np.full(len(labels), .5),
        'threshold_original_0.99': np.full(len(labels), .99),
        'sensitivity_approximately_80_each_label': np.array([
            .48188766837120056, .35740235447883606, .43645793199539185,
            .3550912141799927, .35231277346611023,
        ]),
    }
    report = {'samples': len(targets), 'labels': labels,
              'metric_warning': 'Accuracy is dominated by negatives in this multilabel imbalanced dataset.',
              'scenarios': {name: {'thresholds': dict(zip(labels, values.tolist())),
                                   **summarize(targets, scores, values)}
                            for name, values in scenarios.items()}}
    has_positive = targets.sum(axis=1) > 0
    ranking = np.argsort(-scores, axis=1)
    report['ranking_only_on_images_with_at_least_one_positive_label'] = {
        f'top_{k}_hit': float(np.mean([targets[i, ranking[i, :k]].any()
                                     for i in np.flatnonzero(has_positive)]))
        for k in (1, 2, 3, 5)
    }
    report['ranking_support'] = int(has_positive.sum())
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
