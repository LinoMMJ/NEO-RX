"""Portable session limits and path-independent resume validation."""
import csv
import hashlib
import json
import time
from pathlib import Path


class BudgetExpired(Exception):
    pass


def check_deadline(deadline):
    if deadline is not None and time.monotonic() >= deadline:
        raise BudgetExpired('Session time budget exhausted')


def resume_signature(cfg):
    """Allow mount/output relocation, never changed patients, labels or settings."""
    manifest = Path(cfg['data']['manifest'])
    with manifest.open(encoding='utf-8-sig', newline='') as handle:
        records = sorted((row['Image Index'], row['Patient ID'], row['Finding Labels'],
                          row.get('View Position', ''), row.get('sha256', ''))
                         for row in csv.DictReader(handle))
    config = {key: cfg.get(key) for key in ('target_labels', 'labels_es', 'augmentation', 'threshold', 'decision_strategy')}
    config['model'] = {key: cfg['model'].get(key) for key in ('base_weights', 'num_classes')}
    config['train'] = {key: value for key, value in cfg['train'].items() if key not in ('log_dir', 'num_workers')}
    splits = json.loads(Path(cfg['data']['splits_json']).read_text(encoding='utf-8'))
    payload = json.dumps([records, splits, config], sort_keys=True, ensure_ascii=True).encode()
    return hashlib.sha256(payload).hexdigest()
