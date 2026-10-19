"""Propose thresholds on VALIDATION; report fixed-threshold results on TEST.

This does not retrain, replace the checkpoint or activate a clinical policy.
Unattainable precision/recall targets produce abstention, never a silent fallback.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def decision_metrics(targets, scores, threshold):
    predictions = np.asarray(scores) >= threshold
    truth = np.asarray(targets).astype(bool)
    tp = int((predictions & truth).sum())
    fp = int((predictions & ~truth).sum())
    fn = int((~predictions & truth).sum())
    tn = int((~predictions & ~truth).sum())
    return {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
            'precision': tp / (tp + fp) if tp + fp else None,
            'recall': tp / (tp + fn) if tp + fn else None,
            'specificity': tn / (tn + fp) if tn + fp else None}


def select_threshold(targets, scores, *, min_precision, min_recall, min_predictions):
    truth, values = np.asarray(targets), np.asarray(scores, dtype=float)
    if truth.ndim != 1 or truth.shape != values.shape or not len(truth):
        raise ValueError('Expected non-empty matching one-dimensional arrays')
    if not np.isin(truth, [0, 1]).all() or not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
        raise ValueError('Expected binary labels and finite scores in [0,1]')
    if not 0 < min_precision <= 1 or not 0 < min_recall <= 1 or min_predictions < 1:
        raise ValueError('Invalid precision, recall or sample support target')
    if truth.sum() in (0, len(truth)):
        return {'status': 'insufficient_classes', 'threshold': None}
    order = np.argsort(-values, kind='stable')
    sorted_scores, sorted_truth = values[order], truth[order]
    # Evaluate the end of every tie group: runtime uses score >= threshold.
    ends = np.r_[np.flatnonzero(np.diff(sorted_scores)), len(values) - 1]
    positive = np.cumsum(sorted_truth)[ends]
    count = ends + 1
    precision = positive / count
    recall = positive / truth.sum()
    feasible = (precision >= min_precision) & (recall >= min_recall) & (count >= min_predictions)
    if not feasible.any():
        return {'status': 'target_not_met', 'threshold': None}
    candidates = np.flatnonzero(feasible)
    # Highest recall under constraints; ties prefer precision, then threshold.
    selected = max(candidates, key=lambda i: (recall[i], precision[i], sorted_scores[ends[i]]))
    threshold = float(sorted_scores[ends[selected]])
    return {'status': 'candidate', 'threshold': threshold,
            'validation': decision_metrics(truth, values, threshold)}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cuda')
    parser.add_argument('--min-precision', type=float, required=True)
    parser.add_argument('--min-recall', type=float, required=True)
    parser.add_argument('--min-predictions', type=int, default=30)
    args = parser.parse_args()
    # Validate targets before any expensive inference.
    select_threshold([0, 1], [0.1, 0.9], min_precision=args.min_precision,
                     min_recall=args.min_recall, min_predictions=args.min_predictions)
    import torch
    import yaml
    from training.dataset import get_dataloaders, PATIENT_COLUMN
    from training.evaluate import evaluate_model
    from diagnostico.services import _ResNet50FineTuned
    cfg = yaml.safe_load(args.config.read_text(encoding='utf-8'))
    train, val, test = get_dataloaders(cfg, Path(cfg['data']['splits_json']), Path(cfg['data']['data_dir']))
    patient_sets = [set(loader.dataset.df[PATIENT_COLUMN].astype(str)) for loader in (train, val, test)]
    if any(not patients for patients in patient_sets) or any(patient_sets[i] & patient_sets[j] for i, j in ((0, 1), (0, 2), (1, 2))):
        raise ValueError('Need non-empty, patient-disjoint train, validation and test splits')
    ckpt = torch.load(args.checkpoint, map_location='cpu', weights_only=False)
    labels = ckpt['pathologies']
    if labels != val.dataset.labels:
        raise ValueError('Dataset class order does not match checkpoint')
    model = _ResNet50FineTuned(len(labels), ckpt['state_dict'].get('op_threshs'))
    model.load_state_dict(ckpt['state_dict'], strict=True)
    model.to(torch.device(args.device)).eval()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    print('Inferring VALIDATION at 512 px, without augmentation...', flush=True)
    val_targets, val_scores, _ = evaluate_model(model, val, torch.device(args.device))
    np.savez_compressed(args.output_dir / 'validation_predictions.npz', targets=val_targets, scores=val_scores, labels=labels)
    proposals = {label: select_threshold(val_targets[:, i], val_scores[:, i],
                    min_precision=args.min_precision, min_recall=args.min_recall,
                    min_predictions=args.min_predictions) for i, label in enumerate(labels)}
    # Selection is finished before reading TEST predictions. Never tune on TEST.
    print('Evaluating frozen proposals on TEST...', flush=True)
    test_targets, test_scores, _ = evaluate_model(model, test, torch.device(args.device))
    for i, label in enumerate(labels):
        old_threshold = ckpt.get('thresholds', {}).get(label, 0.5)
        proposals[label]['current_test'] = decision_metrics(test_targets[:, i], test_scores[:, i], old_threshold)
        if proposals[label]['threshold'] is not None:
            proposals[label]['candidate_test'] = decision_metrics(test_targets[:, i], test_scores[:, i], proposals[label]['threshold'])
    report = {'status': 'proposal_not_deployed', 'selection_split': 'validation',
              'checkpoint_sha256': hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
              'input_size': 512, 'calibrated_probabilities': False,
              'targets': {'precision': args.min_precision, 'recall': args.min_recall, 'min_predictions': args.min_predictions},
              'per_class': proposals,
              'note': 'Review precision/recall tradeoffs on independent data. A threshold changes decisions, not calibrated probabilities.'}
    (args.output_dir / 'decision_proposal.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print('Saved decision_proposal.json; original checkpoint unchanged.', flush=True)


if __name__ == '__main__':
    main()
