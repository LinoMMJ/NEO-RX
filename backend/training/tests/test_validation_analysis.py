import hashlib
import json

import numpy as np
import pytest

from training import analyze_validation as analysis
from training.tests.test_frozen_evaluation import setup_run


def test_ties_and_candidate_counts_match_actual_predictions():
    y = np.array([1, 0, 1, 1, 0, 0])
    scores = np.array([.9, .9, .7, .2, .1, .1])
    points = analysis.operating_points(y, scores)
    assert [p['threshold'] for p in points] == [.9, .7, .2, .1]
    for p in points:
        predicted = scores >= p['threshold']
        assert p['tp'] == int((predicted & (y == 1)).sum())
        assert p['fp'] == int((predicted & (y == 0)).sum())
        assert p['fn'] == int((~predicted & (y == 1)).sum())
    for p in analysis.exploratory_candidates(points):
        assert p['threshold'] == .2
        assert p['sensitivity'] >= p['sensitivity_target']
        assert p['fp'] == 1
        assert p['enabled'] is False


def test_invalid_predictions_are_not_reported_as_success():
    with pytest.raises(ValueError):
        analysis.operating_points([0, 1], [.1, np.nan])
    with pytest.raises(ValueError):
        analysis.operating_points([1, 1], [.1, .5])


def setup_validation(tmp_path, monkeypatch):
    from training import kaggle_run
    previous, data, output, _ = setup_run(tmp_path, monkeypatch)
    monkeypatch.setattr(kaggle_run, 'verify_bundle', lambda _: {})
    checkpoint = previous / 'checkpoints/best.pt'
    before = checkpoint.read_bytes()
    digest = hashlib.sha256(before).hexdigest()
    manifest = (previous / 'manifests/clean_manifest.csv').read_text()
    splits = json.loads((previous / 'manifests/splits.json').read_text())
    identity = analysis.dataset_identity(manifest, splits)
    return previous, data, output, digest, identity, before


def test_only_validation_pixels_are_read_and_frozen_model_is_preserved(tmp_path, monkeypatch):
    previous, data, output, digest, identity, before = setup_validation(tmp_path, monkeypatch)
    # Missing TRAIN/TEST pixels must not trigger reading those partitions.
    (data / '0.png').unlink()
    (data / '2.png').unlink()
    cfg, checkpoint, frame, labels, thresholds = analysis.prepare_validation(
        tmp_path, previous, output, data, digest, identity)
    assert frame['Image Index'].tolist() == ['1.png']
    assert labels == ['Effusion'] and thresholds == {'Effusion': .83}
    assert checkpoint.read_bytes() == before
    provenance = json.loads((output / 'provenance.json').read_text())
    assert provenance['test_inference_performed'] is False
    assert provenance['deployment_enabled'] is False


def test_rejects_changed_validation_pixels(tmp_path, monkeypatch):
    previous, data, output, digest, identity, _ = setup_validation(tmp_path, monkeypatch)
    (data / '1.png').write_bytes(b'changed')
    with pytest.raises(ValueError, match='VALIDATION image changed'):
        analysis.prepare_validation(tmp_path, previous, output, data, digest, identity)


def test_rejects_different_checkpoint_and_partition_identity(tmp_path, monkeypatch):
    previous, data, output, digest, identity, _ = setup_validation(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match='Checkpoint differs'):
        analysis.prepare_validation(tmp_path, previous, output, data, '0'*64, identity)
    splits_path = previous / 'manifests/splits.json'
    splits = json.loads(splits_path.read_text())
    splits['val'], splits['test'] = splits['test'], splits['val']
    splits_path.write_text(json.dumps(splits))
    with pytest.raises(ValueError, match='Dataset identity differs'):
        analysis.prepare_validation(tmp_path, previous, output, data, digest, identity)


def test_complete_report_exports_all_scores_and_does_not_enable_policy(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import pandas as pd
    import torch
    from training import evaluate, model
    labels = ['Effusion']
    ids = [f'{i}.png' for i in range(5)]
    frame = pd.DataFrame({'Image Index': ids, 'Finding Labels': ['Effusion', 'No Finding',
                        'Effusion', 'No Finding', 'Effusion']})
    targets = np.array([[1], [0], [1], [0], [1]])
    scores = np.array([[.91], [.91], [.73], [.1], [.4]])
    checkpoint = tmp_path / 'unchanged.pt'
    checkpoint.write_bytes(b'frozen')
    monkeypatch.setattr(analysis, 'prepare_validation', lambda *args: (
        {'model': {'base_weights': 'resnet50-res512-all'}}, checkpoint, frame, labels, {'Effusion': .99}))
    monkeypatch.setattr(torch.cuda, 'is_available', lambda: True)
    monkeypatch.setattr(model, 'load_finetuned_model', lambda *args, **kwargs:
                        SimpleNamespace(to=lambda device: object()))
    monkeypatch.setattr(evaluate, 'evaluate_model', lambda *args: (targets, scores, ids))
    args = SimpleNamespace(data_root=tmp_path, bundle=tmp_path, previous=tmp_path, output=tmp_path,
                           expected_checkpoint='ignored_in_report_test', expected_data='ignored_in_report_test')
    analysis.run(args)
    saved = np.load(tmp_path / 'validation_predictions.npz', allow_pickle=False)
    np.testing.assert_array_equal(saved['probabilities'], scores)
    assert saved['image_ids'].tolist() == ids
    candidates = pd.read_csv(tmp_path / 'comparacion_sensibilidad.csv')
    assert not candidates['enabled'].any()
    assert (candidates['tp'] + candidates['fp'] + candidates['fn'] + candidates['tn']).eq(5).all()
    baseline = pd.read_csv(tmp_path / 'umbrales_originales_VALIDACION.csv')
    assert baseline['precision'].isna().all()  # No emission is undefined precision, not fabricated zero.
    assert (tmp_path / 'sensibilidad_falsas_alarmas.png').stat().st_size > 1000
    assert checkpoint.read_bytes() == b'frozen'
