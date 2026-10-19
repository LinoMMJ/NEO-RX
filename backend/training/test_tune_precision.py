import pytest
from training.tune_precision import select_threshold, decision_metrics


def test_precision_target_reduces_false_positives_with_measured_recall():
    y, p = [1, 0, 1, 0, 0, 0], [0.95, 0.8, 0.9, 0.7, 0.6, 0.2]
    result = select_threshold(y, p, min_precision=0.9, min_recall=0.5, min_predictions=2)
    assert result['threshold'] == 0.9
    assert result['validation']['precision'] == 1
    assert result['validation']['recall'] == 1
    assert result['validation']['fp'] < decision_metrics(y, p, 0.5)['fp']


def test_tied_scores_cannot_create_fake_precision():
    result = select_threshold([1, 0, 0], [0.9, 0.9, 0.2], min_precision=0.9, min_recall=0.5, min_predictions=1)
    assert result == {'status': 'target_not_met', 'threshold': None}


def test_no_fallback_if_target_or_support_unattainable():
    assert select_threshold([1, 0], [0.9, 0.1], min_precision=0.8, min_recall=0.2, min_predictions=30)['threshold'] is None
    assert select_threshold([0, 0], [0.9, 0.1], min_precision=0.8, min_recall=0.2, min_predictions=1)['status'] == 'insufficient_classes'


@pytest.mark.parametrize('scores', [[float('nan'), 0.2], [1.1, 0.2]])
def test_rejects_invalid_scores(scores):
    with pytest.raises(ValueError):
        select_threshold([1, 0], scores, min_precision=0.8, min_recall=0.2, min_predictions=1)
