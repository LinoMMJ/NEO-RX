from types import SimpleNamespace

import numpy as np
import pytest
import torch

from diagnostico.gradcam import GeneradorGradCAM
from diagnostico.pretrained_policy import pretrained_result
from diagnostico.results import probabilities_es, threshold_findings
from diagnostico.services import DetectorTorax


NAMES = {
    'Effusion': 'Derrame pleural', 'Atelectasis': 'Atelectasia',
    'Mass': 'Masa pulmonar', 'Nodule': 'Nódulo pulmonar',
    'Pneumonia': 'Neumonía', 'Consolidation': 'Consolidación',
}


def test_effusion_is_the_only_specific_result_even_with_high_atelectasis():
    result = pretrained_result({'Effusion': .91, 'Atelectasis': .99, 'Mass': .95}, NAMES)
    assert result['enfoque']['estado'] == 'hallazgos_prioritarios'
    assert probabilities_es(result) == {'Derrame pleural': .91}
    assert [row['etiqueta_en'] for row in threshold_findings(result)] == ['Effusion']
    assert result['categoria']['estado'] == 'no_concluyente'


def test_remaining_findings_are_reduced_to_one_category_without_disease_names():
    result = pretrained_result({'Effusion': .49, 'Atelectasis': .99, 'Pneumonia': .82, 'Mass': .60}, NAMES)
    assert result['enfoque']['estado'] == 'orientacion_categoria'
    assert result['categoria']['clave'] == 'infecciosa'
    assert result['categoria']['puntuacion_modelo'] == pytest.approx(.82)
    assert result['categoria']['enfermedades'] == []
    assert probabilities_es(result) == {}
    assert result['enfoque']['objetivos_gradcam'] == [
        {'etiqueta_en': 'Pneumonia', 'etiqueta': 'Orientación infecciosa'}
    ]


def test_close_categories_and_low_scores_abstain():
    close = pretrained_result({'Effusion': .2, 'Pneumonia': .82, 'Mass': .78}, NAMES)
    low = pretrained_result({'Effusion': .49, 'Pneumonia': .49, 'Mass': .3}, NAMES)
    assert close['enfoque']['estado'] == 'no_concluyente'
    assert close['decision']['titulo'] == 'Categoría no concluyente'
    assert low['decision']['titulo'] == 'Sin señal suficiente'


def test_zero_margin_selects_only_the_strongest_presentation_category():
    result = pretrained_result(
        {'Effusion': .20, 'Pneumonia': .71, 'Mass': .69, 'Fibrosis': .55},
        NAMES,
        category_margin=0.0,
    )
    assert result['decision']['titulo'] == 'Orientación por categoría: Infecciosa'
    assert result['categoria']['clave'] == 'infecciosa'
    assert result['enfoque']['objetivos_gradcam'] == [
        {'etiqueta_en': 'Pneumonia', 'etiqueta': 'Orientación infecciosa'}
    ]


def test_default_baseline_is_resnet50(monkeypatch):
    monkeypatch.delenv('NEORX_MODEL_PATH', raising=False)
    monkeypatch.delenv('NEORX_BASELINE_WEIGHTS', raising=False)
    assert DetectorTorax.configured_input_size() == 512


@pytest.mark.parametrize('threshold', [.39, .96, float('nan')])
def test_invalid_threshold_is_rejected(threshold):
    with pytest.raises(ValueError):
        pretrained_result({'Effusion': .9}, NAMES, minimum_score=threshold)


def test_service_uses_pretrained_policy_without_a_finetuned_checkpoint(monkeypatch):
    labels = ['Atelectasis', 'Effusion', 'Pneumonia', 'Mass']
    model = SimpleNamespace(pathologies=labels)
    monkeypatch.setenv('NEORX_DECISION_MODE', 'pretrained_effusion_categories')
    monkeypatch.setenv('NEORX_BASELINE_MIN_SCORE', '0.50')
    monkeypatch.setattr(DetectorTorax, 'cargar', classmethod(lambda cls: model))
    monkeypatch.setattr(DetectorTorax, '_preprocesar', classmethod(lambda cls, image, maximum: torch.zeros(1, 1, 2, 2)))
    monkeypatch.setattr(DetectorTorax, '_labels_es', NAMES)
    monkeypatch.setattr(DetectorTorax, '_is_finetuned', False)
    monkeypatch.setattr(GeneradorGradCAM, 'forward', lambda model, tensor: torch.tensor([[.99, .49, .81, .60]]))
    result = DetectorTorax.predecir(np.zeros((2, 2)), 255)
    assert result['enfoque']['estado'] == 'orientacion_categoria'
    assert result['categoria']['clave'] == 'infecciosa'
    assert result['es_fine_tuned'] is False
    assert len(result['advertencias']) == 2
