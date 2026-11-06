from types import SimpleNamespace

from diagnostico.results import threshold_findings
from informes.views import generar_texto_hallazgos


def test_report_only_lists_candidates_without_destroying_raw_scores():
    data = {'hallazgos': [
        {'etiqueta': 'Fibrosis pulmonar', 'probabilidad_estimada': 0.78, 'threshold_usado': 0.5},
        {'etiqueta': 'Enfisema', 'probabilidad_estimada': 0.61, 'threshold_usado': 0.7},
    ]}
    text = generar_texto_hallazgos(SimpleNamespace(patologias=data), 'PA')
    assert 'Señal compatible con fibrosis pulmonar' in text
    assert 'Enfisema' not in text
    assert len(data['hallazgos']) == 2
    assert '78.0%' not in text
    assert '78.0/100' not in text
    assert data['hallazgos'][0]['probabilidad_estimada'] == 0.78


def test_abstention_is_not_reported_as_missing_thresholds():
    from informes.views import generar_impresion
    result = SimpleNamespace(patologias={
        'hallazgos': [], 'categoria': {
            'estado': 'no_concluyente', 'clave': None,
            'mensaje': 'Ninguna categoría alcanzó criterios de decisión validados.',
        },
    })
    text = generar_texto_hallazgos(result, 'PA')
    assert 'Resultado no concluyente' in text
    assert 'no conserva umbrales' not in text
    assert 'tres hallazgos' not in generar_impresion(result)


def test_multiple_signals_do_not_become_a_single_diagnosis():
    data = {'hallazgos': [
        {'etiqueta': 'Fibrosis pulmonar', 'probabilidad_estimada': 0.78, 'threshold_usado': 0.5},
        {'etiqueta': 'Enfisema', 'probabilidad_estimada': 0.61, 'threshold_usado': 0.6},
    ]}
    assert 'Múltiples señales' in generar_texto_hallazgos(SimpleNamespace(patologias=data), 'PA')
    assert threshold_findings({'Fibrosis pulmonar': 0.99}) == []
