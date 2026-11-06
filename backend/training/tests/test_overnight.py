import copy
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
import yaml

from training.session import BudgetExpired, check_deadline, resume_signature
from training.kaggle_run import discover_data_root, package_outputs, verify_bundle


def config(tmp_path):
    manifest = tmp_path / 'manifest.csv'
    pd.DataFrame([{'Image Index': 'a.png', 'Patient ID': '1', 'Finding Labels': 'Effusion',
                   'View Position': 'PA', 'sha256': 'abc', 'image_path': '/old/a.png'}]).to_csv(manifest, index=False)
    splits = tmp_path / 'splits.json'
    splits.write_text(json.dumps({'train': ['a.png'], 'val': [], 'test': []}))
    return {
        'data': {'manifest': str(manifest), 'splits_json': str(splits), 'data_dir': str(tmp_path)},
        'target_labels': ['Effusion'], 'labels_es': {'Effusion': 'Derrame pleural'},
        'model': {'base_weights': 'resnet50-res512-all', 'num_classes': 1,
                  'checkpoint_dir': str(tmp_path / 'checkpoints'), 'checkpoint_name': 'final.pt'},
        'train': {'seed': 42, 'batch_size': 2, 'num_workers': 0, 'log_dir': str(tmp_path / 'runs'),
                  'epochs_head': 1, 'epochs_finetune': 2, 'lr_head': .001, 'lr_finetune': .001,
                  'weight_decay': .0001, 'grad_clip': 1, 'mixed_precision': False, 'use_pos_weight': True,
                  'early_stopping_patience': 6, 'selection_metric': 'primary_average_precision'},
        'decision_strategy': {'type': 'priority_then_category_v1', 'primary_labels': ['Effusion']},
        'threshold': {'method': 'precision_recall_guarded', 'min_positive_support': 1},
    }


def test_resume_identity_ignores_mounts_but_rejects_data_or_learning_changes(tmp_path):
    cfg = config(tmp_path)
    before = resume_signature(cfg)
    relocated = copy.deepcopy(cfg)
    relocated['model']['checkpoint_dir'] = '/another/place'
    relocated['train']['log_dir'] = '/another/log'
    relocated['train']['num_workers'] = 4
    frame = pd.read_csv(cfg['data']['manifest'])
    frame['image_path'] = '/new/a.png'
    frame.to_csv(cfg['data']['manifest'], index=False)
    assert resume_signature(relocated) == before
    relocated['train']['batch_size'] = 8
    assert resume_signature(relocated) != before
    frame['Patient ID'] = 2
    frame.to_csv(cfg['data']['manifest'], index=False)
    assert resume_signature(cfg) != before


def test_deadline_and_ambiguous_input(tmp_path):
    with pytest.raises(BudgetExpired):
        check_deadline(-1)
    check_deadline(None)
    with pytest.raises(ValueError):
        discover_data_root(tmp_path)
    (tmp_path / 'Data_Entry_2017.csv').write_text('test')
    assert discover_data_root(tmp_path) == tmp_path
    (tmp_path / 'other').mkdir()
    (tmp_path / 'other/Data_Entry_2017.csv').write_text('test')
    with pytest.raises(ValueError):
        discover_data_root(tmp_path)


def test_bundle_detects_tampering_and_outputs_do_not_include_other_folders(tmp_path):
    import hashlib
    import zipfile
    (tmp_path / 'code.py').write_bytes(b'code')
    (tmp_path / 'bundle_manifest.json').write_text(json.dumps({'sha256': {'code.py': hashlib.sha256(b'code').hexdigest()}}))
    verify_bundle(tmp_path)
    (tmp_path / 'code.py').write_bytes(b'changed')
    with pytest.raises(ValueError):
        verify_bundle(tmp_path)
    output = tmp_path / 'run'
    output.mkdir()
    (output / 'STATUS.json').write_text('{}')
    (output / 'partial.pt.tmp').write_text('unfinished')
    (tmp_path / '.env').write_text('not for export')
    archive = package_outputs(output)
    with zipfile.ZipFile(archive) as z:
        assert z.namelist() == ['run/STATUS.json']


class TinyBackbone(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer3 = nn.Linear(2, 3)
        self.layer4 = nn.Linear(3, 3)
        self.fc = nn.Linear(3, 1)

    def forward(self, tensor):
        return self.fc(self.layer4(self.layer3(tensor)))


class TinyModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.model = TinyBackbone()


def test_training_pause_resume_preserves_best_and_finishes(tmp_path, monkeypatch):
    """Actual optimizer + checkpoint I/O; no GPU, model downloads or NIH images."""
    from training import train
    from training.model import load_checkpoint
    torch.set_num_threads(1)
    cfg = config(tmp_path)
    path = tmp_path / 'config.yaml'
    path.write_text(yaml.safe_dump(cfg), encoding='utf-8')
    loader = DataLoader(TensorDataset(torch.tensor([[1., 0.], [0., 1.], [2., 0.], [0., 2.]]),
                                    torch.tensor([[1.], [0.], [1.], [0.]]), torch.arange(4)), batch_size=2)
    monkeypatch.setattr(train, 'get_dataloaders', lambda *a, **k: (loader, loader, loader))
    monkeypatch.setattr(train, 'build_model', lambda cfg: TinyModel())
    real_epoch = train.train_one_epoch

    def interrupt_second(*args, **kwargs):
        if args[8] == 1:
            raise BudgetExpired()
        return real_epoch(*args, **kwargs)

    monkeypatch.setattr(train, 'train_one_epoch', interrupt_second)
    monkeypatch.setattr(sys, 'argv', ['train', '--config', str(path), '--device', 'cpu'])
    train.main()
    folder = tmp_path / 'checkpoints'
    assert json.loads((folder / 'session_status.json').read_text())['status'] == 'paused_time_budget'
    assert not (folder / 'final.pt').exists()
    last = load_checkpoint(folder / 'last.pt')
    assert last['training_state']['next_epoch'] == 1
    assert last['training_state']['optimizer_state']
    best_score = load_checkpoint(folder / 'best.pt')['metrics']['selection_score']
    monkeypatch.setattr(train, 'train_one_epoch', real_epoch)
    monkeypatch.setattr(sys, 'argv', ['train', '--config', str(path), '--device', 'cpu', '--resume', str(folder / 'last.pt')])
    train.main()
    assert json.loads((folder / 'session_status.json').read_text())['training_finished'] is True
    final = load_checkpoint(folder / 'final.pt')
    assert final['metrics']['selection_score'] >= best_score
    assert final['pathologies'] == ['Effusion'] and final['thresholds'] and final['decision_policy']
    assert load_checkpoint(folder / 'last.pt')['training_state']['next_epoch'] == 3


def test_first_epoch_interruption_is_resumable_without_claiming_results(tmp_path, monkeypatch):
    from training import train
    from training.model import load_checkpoint
    cfg = config(tmp_path)
    cfg['train']['use_pos_weight'] = False
    path = tmp_path / 'config.yaml'
    path.write_text(yaml.safe_dump(cfg), encoding='utf-8')
    monkeypatch.setattr(train, 'get_dataloaders', lambda *a, **k: ([], [], []))
    monkeypatch.setattr(train, 'build_model', lambda cfg: TinyModel())
    monkeypatch.setattr(train, 'train_one_epoch', lambda *a, **k: (_ for _ in ()).throw(BudgetExpired()))
    monkeypatch.setattr(sys, 'argv', ['train', '--config', str(path), '--device', 'cpu'])
    train.main()
    folder = tmp_path / 'checkpoints'
    assert load_checkpoint(folder / 'last.pt')['training_state']['next_epoch'] == 0
    assert not (folder / 'best.pt').exists() and not (folder / 'final.pt').exists()
    assert json.loads((folder / 'session_status.json').read_text())['training_finished'] is False


def test_frozen_batchnorm_statistics_do_not_change_during_head_training():
    from training.train import train_one_epoch
    from unittest.mock import MagicMock
    model = TinyModel()
    model.model.layer3 = nn.Sequential(nn.Linear(2, 3), nn.BatchNorm1d(3))
    for parameter in model.model.layer3.parameters():
        parameter.requires_grad = False
    bn = model.model.layer3[1]
    before = bn.running_mean.clone()
    loader = DataLoader(TensorDataset(torch.ones(4, 2), torch.ones(4, 1), torch.arange(4)), batch_size=2)
    optimizer = torch.optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()))
    train_one_epoch(model, loader, optimizer, nn.BCEWithLogitsLoss(), torch.device('cpu'), False,
                    None, 1, 0, MagicMock())
    torch.testing.assert_close(bn.running_mean, before)


def test_kaggle_runner_requires_gpu_and_exports_failure_status(tmp_path, monkeypatch):
    from training import kaggle_run
    monkeypatch.setattr(kaggle_run, 'verify_bundle', lambda _: {'sha256': {}})
    monkeypatch.setattr(torch.cuda, 'is_available', lambda: False)
    output = tmp_path / 'output'
    monkeypatch.setattr(sys, 'argv', ['kaggle_run', '--bundle', str(tmp_path), '--output', str(output)])
    with pytest.raises(RuntimeError, match='GPU'):
        kaggle_run.main()
    status = json.loads((output / 'STATUS.json').read_text())
    assert status['status'] == 'failed' and not status['test_evaluated']
    assert (tmp_path / 'neorx_entrenamiento_resultados.zip').exists()


def test_kaggle_runner_does_not_evaluate_incomplete_training(tmp_path, monkeypatch):
    from training import kaggle_run
    cfg = config(tmp_path)
    bundle = tmp_path / 'bundle'
    (bundle / 'training').mkdir(parents=True)
    (bundle / 'training/config.priority2.v2.kaggle.yaml').write_text(yaml.safe_dump(cfg), encoding='utf-8')
    previous = tmp_path / 'previous'
    (previous / 'checkpoints').mkdir(parents=True)
    (previous / 'checkpoints/session_status.json').write_text(json.dumps({'training_finished': False}))
    (previous / 'config.runtime.yaml').write_text(yaml.safe_dump(cfg), encoding='utf-8')
    (previous / 'source_bundle.json').write_text(json.dumps({'sha256': {}}))
    # Use manifest names expected from the real validator.
    (tmp_path / 'clean_manifest.csv').write_bytes((tmp_path / 'manifest.csv').read_bytes())
    monkeypatch.setattr(kaggle_run, 'verify_bundle', lambda _: {'sha256': {}})
    monkeypatch.setattr(kaggle_run, 'prepare_data', lambda *a: tmp_path)
    monkeypatch.setattr(torch.cuda, 'is_available', lambda: True)
    monkeypatch.setattr(torch.cuda, 'get_device_name', lambda _: 'test GPU')
    monkeypatch.setattr(torch.cuda, 'device_count', lambda: 1)
    monkeypatch.setattr(kaggle_run, 'command', lambda *a: pytest.fail('TEST must not be evaluated'))
    output = tmp_path / 'output'
    monkeypatch.setattr(sys, 'argv', ['kaggle_run', '--bundle', str(bundle), '--output', str(output),
                                    '--previous-output', str(previous), '--data-root', str(tmp_path),
                                    '--mode', 'evaluate', '--batch-size', '2'])
    with pytest.raises(ValueError, match='Finish training'):
        kaggle_run.main()
    assert not json.loads((output / 'STATUS.json').read_text())['test_evaluated']
