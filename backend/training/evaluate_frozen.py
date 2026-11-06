"""Freeze the validation-selected checkpoint after an explicit budget stop.

This separate entry point works with the ORIGINAL Kaggle bundle. It never
alters that bundle, trains, tunes thresholds on TEST or claims 21 epochs ran.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import time

import yaml

from training.analyze_targets import analyze
from training.configuration import get_target_labels
from training.kaggle_run import discover_data_root, package_outputs, verify_bundle, write_json
from training.model import load_checkpoint
from training.session import resume_signature
from training.validate_dataset import index_images


def prepare_evaluation(bundle, previous, output, data_root, close_by_budget):
    build = verify_bundle(bundle)
    if json.loads((previous / 'source_bundle.json').read_text(encoding='utf-8')) != build:
        raise ValueError('Use the ORIGINAL code bundle from training')
    if (previous / 'evaluation').exists():
        raise ValueError('This run already has TEST results; use those results instead of selecting another model')
    state = json.loads((previous / 'checkpoints/session_status.json').read_text(encoding='utf-8'))
    if not state.get('training_finished'):
        if state.get('status') != 'paused_time_budget' or not close_by_budget:
            raise ValueError('Explicit budget closure is required for a paused run')
    cfg = yaml.safe_load((previous / 'config.runtime.yaml').read_text(encoding='utf-8'))
    manifest_text = (previous / 'manifests/clean_manifest.csv').read_text(encoding='utf-8-sig')
    splits = json.loads((previous / 'manifests/splits.json').read_text(encoding='utf-8'))
    analyze(manifest_text, splits)
    folder = output / 'manifests'
    folder.mkdir(parents=True)
    manifest = folder / 'clean_manifest.csv'
    manifest.write_text(manifest_text, encoding='utf-8')
    write_json(folder / 'splits.json', splits)
    cfg['data'].update(data_dir=str(data_root), manifest=str(manifest), splits_json=str(folder / 'splits.json'))
    last = load_checkpoint(previous / 'checkpoints/last.pt')
    if last.get('training_state', {}).get('resume_signature') != resume_signature(cfg):
        raise ValueError('Dataset/configuration identity differs from the saved training run')
    completed = int(last['training_state']['next_epoch'])
    del last
    best_path = previous / 'checkpoints/best.pt'
    best = load_checkpoint(best_path)
    labels = get_target_labels(cfg)
    if best.get('pathologies') != labels:
        raise ValueError('Best checkpoint labels differ from training')
    if best.get('extra', {}).get('config', {}).get('decision_strategy') != cfg.get('decision_strategy'):
        raise ValueError('Best checkpoint routing policy differs from training')
    for label in labels:
        threshold = best.get('thresholds', {}).get(label)
        policy = best.get('decision_policy', {}).get(label)
        if not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
            raise ValueError(f'Missing or invalid validation threshold: {label}')
        if not isinstance(policy, dict) or not isinstance(policy.get('enabled'), bool):
            raise ValueError(f'Missing validation decision policy: {label}')
    selected_epoch = best.get('extra', {}).get('epoch')
    if not isinstance(selected_epoch, int) or not 0 <= selected_epoch < completed:
        raise ValueError('Invalid selected checkpoint epoch')
    target = output / 'checkpoints' / cfg['model']['checkpoint_name']
    target.parent.mkdir()
    shutil.copy2(best_path, target)
    selected_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    record = {
        'status': 'frozen_before_test',
        'closure_reason': 'time_budget' if not state.get('training_finished') else state['status'],
        'original_training_status': state, 'completed_epochs': completed,
        'selected_epoch_zero_based': selected_epoch, 'selected_by': 'VALIDATION primary average precision',
        'checkpoint_sha256': selected_hash, 'thresholds': best['thresholds'],
        'decision_policy': best['decision_policy'], 'validation_metrics': best.get('metrics', {}),
        'note': 'No claim of completing all planned epochs. TEST must not guide further model selection. Internal NIH evaluation, not external clinical validation.',
    }
    write_json(output / 'FREEZE.json', record)
    write_json(output / 'source_bundle.json', build)
    del best

    paths = index_images(data_root)
    with manifest.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    test_ids = set(splits['test'])
    if not test_ids or not all(isinstance(name, str) for name in test_ids):
        raise ValueError('Expected the original named TEST partition')
    test_rows = []
    for row in rows:
        matches = paths.get(row['Image Index'], [])
        if len(matches) != 1:
            raise ValueError(f"Missing/ambiguous dataset file: {row['Image Index']}")
        row['image_path'] = str(matches[0])
        if row['Image Index'] in test_ids:
            test_rows.append(row)

    def verify_pixels(row):
        # Compare TEST bytes against the training audit, not a newly accepted hash.
        digest = hashlib.sha256(Path(row['image_path']).read_bytes()).hexdigest()
        if digest != row.get('sha256'):
            raise ValueError(f"TEST image changed: {row['Image Index']}")

    print(f'Checking the {len(test_rows):,} TEST images against the original audit; no full image re-audit.', flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        for index, _ in enumerate(pool.map(verify_pixels, test_rows), 1):
            if index % 1000 == 0:
                print(f'TEST verified: {index:,}/{len(test_rows):,}', flush=True)
    with manifest.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    cfg['model'].update(cache_dir=str(bundle / 'weights'), checkpoint_dir=str(target.parent))
    runtime = output / 'config.runtime.yaml'
    runtime.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding='utf-8')
    write_json(output / 'input_verification.json', {'test_images_verified': len(test_rows), 'hashes_match_training_audit': True})
    return runtime, target


class ProgressLoader:
    """Report completed inference batches without changing their contents/order."""

    def __init__(self, loader):
        self.loader = loader

    def __iter__(self):
        started = time.monotonic()
        last_report = started
        completed = 0
        total = len(self.loader.dataset)
        for batch in self.loader:
            yield batch
            completed += len(batch[2])
            now = time.monotonic()
            if completed == len(batch[2]) or now - last_report >= 30 or completed == total:
                elapsed = max(now - started, 1e-6)
                rate = completed / elapsed
                remaining = max(0, total - completed) / rate
                print(f'TEST inference: {completed:,}/{total:,} | {rate:.2f} images/s | '
                      f'estimated remaining inference: {remaining / 3600:.2f} h '
                      '(excludes setup, verification and final reports)', flush=True)
                last_report = now


def run_evaluation(config, target, output, device, cpu_threads=2):
    """Use original metrics/inference code, adding only resource limits/progress."""
    import torch
    from training import evaluate as evaluator

    if device == 'cpu':
        torch.set_num_threads(cpu_threads)
        cfg = yaml.safe_load(config.read_text(encoding='utf-8'))
        original_batch = cfg['train']['batch_size']
        original_workers = cfg['train'].get('num_workers', 0)
        # Identity was checked before this evaluation-only resource adjustment.
        cfg['train'].update(batch_size=2, num_workers=2)
        config.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding='utf-8')
        write_json(output / 'evaluation_resources.json', {
            'device': 'cpu', 'threads': cpu_threads, 'batch_size': 2, 'num_workers': 2,
            'original_batch_size': original_batch, 'original_num_workers': original_workers,
            'full_test_set': True, 'image_resolution_unchanged': True,
        })
    original_evaluate = evaluator.evaluate_model
    original_argv = sys.argv

    def with_progress(model, loader, selected_device):
        return original_evaluate(model, ProgressLoader(loader), selected_device)

    try:
        evaluator.evaluate_model = with_progress
        sys.argv = ['training.evaluate', '--config', str(config), '--checkpoint', str(target),
                    '--device', device, '--output-dir', str(output / 'evaluation'), '--plot']
        evaluator.main()
    finally:
        sys.argv = original_argv
        evaluator.evaluate_model = original_evaluate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--previous-output', type=Path, required=True)
    parser.add_argument('--data-root', type=Path)
    parser.add_argument('--output', type=Path, default=Path('/kaggle/working/neorx-evaluation'))
    parser.add_argument('--close-by-budget', action='store_true')
    parser.add_argument('--device', choices=['cuda', 'cpu'], default='cuda')
    parser.add_argument('--cpu-threads', type=int, default=2)
    args = parser.parse_args()
    if args.cpu_threads < 1:
        parser.error('--cpu-threads must be positive')
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a fresh Kaggle version; this evaluation output already exists')
    output.mkdir(parents=True, exist_ok=True)
    status = {'status': 'failed', 'test_evaluated': False}
    try:
        import torch
        if args.device == 'cuda' and not torch.cuda.is_available():
            raise RuntimeError('Enable GPU in Kaggle')
        print(f'Evaluation device: {args.device}. Full TEST set; no training.', flush=True)
        data_root = args.data_root or discover_data_root(Path('/kaggle/input'))
        cfg, target = prepare_evaluation(args.bundle.resolve(), args.previous_output.resolve(), output,
                                         data_root.resolve(), args.close_by_budget)
        run_evaluation(cfg, target, output, args.device, args.cpu_threads)
        status = {'status': 'evaluated', 'test_evaluated': True, 'training_run_frozen': True,
                  'note': 'Review metrics and routing_summary.json before considering deployment; evaluation does not improve weights.'}
        print(json.dumps(status, indent=2), flush=True)
    except BaseException as exc:
        status['error'] = str(exc)
        raise
    finally:
        write_json(output / 'STATUS.json', status)
        package_outputs(output)


if __name__ == '__main__':
    main()
