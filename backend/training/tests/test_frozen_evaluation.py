import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
import torch
import yaml

from training import evaluate_frozen as frozen
from training.session import resume_signature


def setup_run(tmp_path, monkeypatch):
    previous = tmp_path / 'previous'
    (previous / 'manifests').mkdir(parents=True)
    (previous / 'checkpoints').mkdir()
    data = tmp_path / 'data'
    data.mkdir()
    rows = []
    for i in range(3):
        path = data / f'{i}.png'
        payload = f'unique test bytes {i}'.encode()
        path.write_bytes(payload)
        rows.append({'Image Index': path.name, 'Patient ID': str(i), 'Finding Labels': 'Effusion',
                     'View Position': 'PA', 'image_path': f'/old/{path.name}',
                     'sha256': hashlib.sha256(payload).hexdigest()})
    manifest = previous / 'manifests/clean_manifest.csv'
    pd.DataFrame(rows).to_csv(manifest, index=False)
    splits = previous / 'manifests/splits.json'
    splits.write_text(json.dumps({'train': ['0.png'], 'val': ['1.png'], 'test': ['2.png']}))
    cfg = {'data': {'manifest': str(manifest), 'splits_json': str(splits)},
           'model': {'base_weights': 'resnet50-res512-all', 'num_classes': 1, 'checkpoint_name': 'final.pt'},
           'train': {'seed': 42, 'batch_size': 16}, 'target_labels': ['Effusion'],
           'decision_strategy': {'type': 'priority_then_category_v1', 'primary_labels': ['Effusion']}}
    (previous / 'config.runtime.yaml').write_text(yaml.safe_dump(cfg), encoding='utf-8')
    (previous / 'source_bundle.json').write_text('{}')
    state = {'status': 'paused_time_budget', 'training_finished': False, 'next_epoch': 12, 'total_epochs': 21}
    (previous / 'checkpoints/session_status.json').write_text(json.dumps(state))
    torch.save({'training_state': {'next_epoch': 12, 'resume_signature': resume_signature(cfg)}}, previous / 'checkpoints/last.pt')
    best = {'state_dict': {'weight': torch.tensor([7.])}, 'pathologies': ['Effusion'],
            'extra': {'epoch': 7, 'config': cfg}, 'thresholds': {'Effusion': .83},
            'decision_policy': {'Effusion': {'enabled': False}}, 'metrics': {'selection_score': .522}}
    torch.save(best, previous / 'checkpoints/best.pt')
    monkeypatch.setattr(frozen, 'verify_bundle', lambda _: {})
    output = tmp_path / 'output'
    output.mkdir()
    return previous, data, output, best


def test_budget_closure_preserves_best_weights_and_truthful_training_status(tmp_path, monkeypatch):
    previous, data, output, _ = setup_run(tmp_path, monkeypatch)
    config, target = frozen.prepare_evaluation(tmp_path, previous, output, data, True)
    assert target.read_bytes() == (previous / 'checkpoints/best.pt').read_bytes()
    record = json.loads((output / 'FREEZE.json').read_text())
    assert record['completed_epochs'] == 12 and record['selected_epoch_zero_based'] == 7
    assert record['closure_reason'] == 'time_budget'
    assert not record['original_training_status']['training_finished']
    assert record['decision_policy']['Effusion']['enabled'] is False
    runtime = yaml.safe_load(config.read_text())
    assert runtime['target_labels'] == ['Effusion']
    verify = json.loads((output / 'input_verification.json').read_text())
    assert verify['test_images_verified'] == 1


def test_frozen_evaluation_rejects_modified_test_pixels(tmp_path, monkeypatch):
    previous, data, output, _ = setup_run(tmp_path, monkeypatch)
    (data / '2.png').write_bytes(b'changed')
    with pytest.raises(ValueError, match='TEST image changed'):
        frozen.prepare_evaluation(tmp_path, previous, output, data, True)


def test_budget_closure_requires_explicit_intent(tmp_path, monkeypatch):
    previous, data, output, _ = setup_run(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match='Explicit budget closure'):
        frozen.prepare_evaluation(tmp_path, previous, output, data, False)


def test_frozen_evaluation_does_not_invent_missing_thresholds(tmp_path, monkeypatch):
    previous, data, output, best = setup_run(tmp_path, monkeypatch)
    best['thresholds'] = {}
    torch.save(best, previous / 'checkpoints/best.pt')
    with pytest.raises(ValueError, match='validation threshold'):
        frozen.prepare_evaluation(tmp_path, previous, output, data, True)


def test_cpu_evaluation_keeps_all_samples_thresholds_and_reports_progress(tmp_path, monkeypatch, capsys):
    import sys
    from torch.utils.data import DataLoader
    from training import evaluate as evaluator

    config = tmp_path / 'config.yaml'
    config.write_text(yaml.safe_dump({
        'train': {'batch_size': 16, 'num_workers': 2},
        'data': {'data_dir': str(tmp_path), 'splits_json': str(tmp_path / 'splits.json')},
        'model': {}, 'target_labels': ['Effusion'],
    }))
    # An odd sample count catches accidental loss of the last partial batch.
    samples = [(torch.tensor([value]), torch.tensor([target]), f'{i}.png')
               for i, (value, target) in enumerate([(-2., 0.), (2., 1.), (1., 0.), (-1., 1.), (3., 1.)])]
    observed = {}

    def loaders(cfg, *_):
        observed['batch_size'] = cfg['train']['batch_size']
        return None, None, DataLoader(samples, batch_size=cfg['train']['batch_size'])

    model = torch.nn.Module()
    model.model = torch.nn.Identity()
    model.pathologies = ['Effusion']
    model.decision_strategy = None
    monkeypatch.setattr(evaluator, 'get_dataloaders', loaders)
    monkeypatch.setattr(evaluator, 'load_finetuned_model', lambda *a, **k: model)
    monkeypatch.setattr(evaluator, 'get_thresholds_from_checkpoint', lambda _: {'Effusion': .83})
    for name in ['plot_roc_curves', 'plot_pr_curves', 'plot_confusion_matrices']:
        monkeypatch.setattr(evaluator, name, lambda *a, **k: None)
    original_evaluate, original_argv = evaluator.evaluate_model, sys.argv
    previous_threads = torch.get_num_threads()
    try:
        frozen.run_evaluation(config, tmp_path / 'best.pt', tmp_path, 'cpu', 2)
    finally:
        torch.set_num_threads(previous_threads)
    report = json.loads((tmp_path / 'evaluation/classification_report.json').read_text())
    assert report['test_samples'] == 5
    assert report['per_class']['Effusion']['threshold'] == .83
    assert report['per_class']['Effusion']['confusion_matrix'] == [[2, 0], [1, 2]]
    assert observed['batch_size'] == 2
    assert 'TEST inference: 5/5' in capsys.readouterr().out
    assert evaluator.evaluate_model is original_evaluate and sys.argv is original_argv
    resources = json.loads((tmp_path / 'evaluation_resources.json').read_text())
    assert resources['full_test_set'] and resources['original_batch_size'] == 16


def test_evaluation_restores_original_entry_points_after_failure(tmp_path, monkeypatch):
    import sys
    from training import evaluate as evaluator

    def fail():
        raise RuntimeError('inference failed')

    monkeypatch.setattr(evaluator, 'main', fail)
    original_evaluate, original_argv = evaluator.evaluate_model, sys.argv
    with pytest.raises(RuntimeError, match='inference failed'):
        frozen.run_evaluation(tmp_path / 'unused.yaml', tmp_path / 'best.pt', tmp_path, 'cuda')
    assert evaluator.evaluate_model is original_evaluate and sys.argv is original_argv
