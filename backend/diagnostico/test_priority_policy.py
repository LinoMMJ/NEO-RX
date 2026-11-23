from types import SimpleNamespace
import pytest
from diagnostico.priority_policy import CATEGORY_HEADS, PRIMARY_LABELS, STRATEGY, priority_result, expanded_labels, add_experimental_orientation
from diagnostico.results import probabilities_es, threshold_findings

NAMES = {'Effusion': 'Derrame pleural', 'Atelectasis': 'Atelectasia'}
LABELS = [*PRIMARY_LABELS, *CATEGORY_HEADS]


def decide(**overrides):
    scores = {label: 0.1 for label in LABELS}
    scores.update(overrides)
    return priority_result(scores, {label: 0.6 for label in LABELS},
                           {label: {'enabled': True} for label in LABELS}, NAMES,
                           {'type': STRATEGY, 'primary_labels': PRIMARY_LABELS, 'category_margin': 0.1})


def test_specialist_precedes_category_even_when_category_score_is_higher():
    result = decide(Effusion=0.85, CategoryTumoral=0.99)
    assert result['enfoque']['estado'] == 'hallazgos_prioritarios'
    assert probabilities_es(result) == {'Derrame pleural': 0.85}
    assert result['categoria']['estado'] != 'seleccionada'
    assert result['enfoque']['objetivos_gradcam'] == [{'etiqueta_en': 'Effusion', 'etiqueta': 'Derrame pleural'}]


def test_two_primary_findings_can_coexist():
    result = decide(Effusion=0.85, Atelectasis=0.9)
    assert len(threshold_findings(result)) == 2
    assert set(probabilities_es(result)) == {'Derrame pleural', 'Atelectasia'}


def test_category_fallback_does_not_invent_a_specific_disease():
    from informes.views import generar_texto_hallazgos, generar_impresion
    result = decide(CategoryTumoral=0.95)
    assert result['enfoque']['estado'] == 'orientacion_categoria'
    assert result['categoria']['clave'] == 'tumoral'
    assert result['enfoque']['objetivos_gradcam'][0]['etiqueta_en'] == 'CategoryTumoral'
    assert probabilities_es(result) == {}
    assert threshold_findings(result) == []
    assert 'no significa' in result['decision']['mensaje']
    assert 'Categoría principal: Tumoral' in generar_texto_hallazgos(SimpleNamespace(patologias=result), 'PA')
    assert 'categoría principal Tumoral' in generar_impresion(SimpleNamespace(patologias=result))
    assert 'resultado no concluyente' not in generar_impresion(SimpleNamespace(patologias=result))


@pytest.mark.parametrize('primary', [None, 1, ['Effusion', {}], 'Effusion'])
def test_invalid_primary_metadata_fails_closed(primary):
    result = priority_result({}, {}, {}, NAMES, {'type': STRATEGY, 'primary_labels': primary})
    assert result['enfoque']['estado'] == 'modelo_pendiente_validacion'
    assert result['enfoque']['objetivos_gradcam'] == []


def test_test_evaluation_uses_same_router_and_disabled_policies():
    pytest.importorskip('sklearn', reason='Dependencia disponible solo en el entorno de entrenamiento')
    import numpy as np
    from training.evaluate import routing_summary
    targets = np.asarray([[1, 0, 0, 1, 0, 0], [0, 0, 1, 0, 0, 0], [0, 0, 0, 0, 0, 0]])
    probs = np.asarray([[.9, .1, .1, .9, .1, .1], [.1, .1, .9, .1, .1, .1], [.1] * 6])
    kwargs = (targets, probs, LABELS, {label: .6 for label in LABELS})
    strategy = {'type': STRATEGY, 'primary_labels': PRIMARY_LABELS}
    summary = routing_summary(*kwargs, {label: {'enabled': True} for label in LABELS}, strategy)
    assert summary['primary']['Effusion']['precision'] == 1
    assert summary['category_fallback_label_agreement'] == 1
    assert summary['states'] == {'hallazgos_prioritarios': 1, 'orientacion_categoria': 1, 'no_concluyente': 1}
    assert routing_summary(*kwargs, {}, strategy)['states'] == {'modelo_pendiente_validacion': 3}


def test_close_categories_abstain():
    result = decide(CategoryTumoral=0.9, CategoryPleural=0.89)
    assert result['enfoque']['estado'] == 'no_concluyente'
    assert result['categoria']['clave'] is None


def test_low_scores_do_not_mean_normal():
    result = decide()
    assert result['enfoque']['estado'] == 'no_concluyente'
    assert 'no confirma ni descarta' in result['decision']['mensaje']


def test_old_checkpoint_cannot_claim_new_specialist_flow():
    result = priority_result({'Effusion': 0.99}, {'Effusion': 0.5}, {'Effusion': {'enabled': True}}, NAMES)
    assert result['enfoque']['estado'] == 'modelo_pendiente_validacion'
    assert probabilities_es(result) == {}


def test_missing_validation_policy_disables_all_decisions():
    result = priority_result({label: 0.99 for label in LABELS}, {label: 0.5 for label in LABELS}, {}, NAMES,
                             {'type': STRATEGY, 'primary_labels': PRIMARY_LABELS})
    assert result['enfoque']['estado'] == 'modelo_pendiente_validacion'


def test_demo_orientation_exposes_top_category_without_enabling_clinical_decisions():
    scores = {
        'Effusion': 0.10, 'Atelectasis': 0.10,
        'CategoryTumoral': 0.40, 'CategoryPleural': 0.25,
        'CategoryInfectious': 0.32, 'CategoryInterstitial': 0.51,
    }
    closed = priority_result(
        scores, {label: 0.99 for label in LABELS}, {}, NAMES,
        {'type': STRATEGY, 'primary_labels': PRIMARY_LABELS},
    )
    result = add_experimental_orientation(closed, scores, NAMES, 0.50, 0.08)
    assert result['enfoque']['estado'] == 'orientacion_categoria_experimental'
    assert result['categoria']['clave'] == 'intersticial'
    assert result['categoria']['validada'] is False
    assert not any(row['decision_habilitada'] for row in result['hallazgos'])


@pytest.mark.parametrize('compatible', [True, False])
def test_inference_service_routes_new_mode_without_relabeling_old_weights(monkeypatch, compatible):
    import numpy as np
    import torch
    from diagnostico.services import DetectorTorax
    from diagnostico.gradcam import GeneradorGradCAM
    labels = LABELS if compatible else ['Effusion', 'Mass']
    model = SimpleNamespace(pathologies=labels)
    monkeypatch.setenv('NEORX_DECISION_MODE', 'priority_category')
    monkeypatch.setattr(DetectorTorax, 'cargar', classmethod(lambda cls: model))
    monkeypatch.setattr(DetectorTorax, '_preprocesar', classmethod(lambda cls, image, maximum: torch.zeros(1, 1, 2, 2)))
    monkeypatch.setattr(DetectorTorax, '_thresholds', {label: .6 for label in labels})
    monkeypatch.setattr(DetectorTorax, '_decision_policy', {label: {'enabled': True} for label in labels})
    monkeypatch.setattr(DetectorTorax, '_labels_es', NAMES)
    monkeypatch.setattr(DetectorTorax, '_is_finetuned', True)
    monkeypatch.setattr(DetectorTorax, '_decision_strategy', {'type': STRATEGY, 'primary_labels': PRIMARY_LABELS} if compatible else None)
    monkeypatch.setattr(GeneradorGradCAM, 'forward', lambda model, tensor: torch.tensor([[2.] + [-2.] * (len(labels) - 1)]))
    result = DetectorTorax.predecir(np.zeros((2, 2)), 255)
    assert result['enfoque']['estado'] == ('hallazgos_prioritarios' if compatible else 'modelo_pendiente_validacion')
    assert bool(result['enfoque']['hallazgos_detectados']) is compatible


def test_derived_category_targets_preserve_coexisting_findings():
    found = expanded_labels('Atelectasis|Effusion|Mass|Consolidation')
    assert {'Atelectasis', 'Effusion', 'CategoryPleural', 'CategoryTumoral', 'CategoryInfectious'} <= found
    assert 'CategoryInterstitial' not in found
    assert expanded_labels('No Finding') == {'No Finding'}


def test_training_dataset_and_splitter_use_same_six_targets():
    pytest.importorskip('sklearn', reason='Dependencia disponible solo en el entorno de entrenamiento')
    import pandas as pd
    from training.dataset import parse_finding_labels
    from training.create_splits import label_matrix
    labels = parse_finding_labels('Atelectasis|Effusion', set(LABELS))
    matrix = label_matrix(pd.DataFrame({'Finding Labels': ['Atelectasis|Effusion']}), LABELS)
    assert set(labels) == {name for name, value in zip(LABELS, matrix[0]) if value}
    assert matrix.tolist() == [[1, 1, 0, 1, 0, 0]]


def test_frequency_selection_is_based_on_train_and_rejects_leakage():
    from training.analyze_targets import analyze
    metadata = 'Image Index,Finding Labels,Patient ID\na,Effusion,1\nb,Atelectasis,2\nc,Mass,3\nd,Mass,4\ne,Mass,5\n'
    split = {'train': ['a', 'b'], 'val': ['c'], 'test': ['d', 'e']}
    assert set(analyze(metadata, split)['selected_targets']) == {'Effusion', 'Atelectasis'}
    with pytest.raises(ValueError, match='overlap'):
        analyze(metadata.replace('e,Mass,5', 'e,Mass,1'), split)


def test_new_training_config_has_complete_priority_contract():
    from pathlib import Path
    import yaml
    from training.configuration import get_target_labels
    config = yaml.safe_load((Path(__file__).parents[1] / 'training/config.priority2.kaggle.yaml').read_text(encoding='utf-8'))
    assert get_target_labels(config) == ['Effusion', *CATEGORY_HEADS]
    assert config['decision_strategy']['type'] == STRATEGY
    assert config['decision_strategy']['primary_labels'] == ['Effusion']
    assert config['train']['selection_metric'] == 'primary_average_precision'
