from types import SimpleNamespace

from diagnostico.results import threshold_findings
from informes.views import generar_texto_hallazgos


def test_report_only_lists_candidates_without_destroying_raw_scores():
    data = {'hallazgos': [
        {'etiqueta': 'Fibrosis pulmonar', 'probabilidad_estimada': 0.78, 'threshold_usado': 0.5},
        {'etiqueta': 'Enfisema', 'probabilidad_estimada': 0.61, 'threshold_usado': 0.7},
    ]}
    text = generar_texto_hallazgos(SimpleNamespace(patologias=data), 'PA')
    assert 'Fibrosis pulmonar: señal 78.0/100' in text
    assert 'Enfisema' not in text
    assert len(data['hallazgos']) == 2
    assert '78.0%' not in text


def test_multiple_signals_do_not_become_a_single_diagnosis():
    data = {'hallazgos': [
        {'etiqueta': 'Fibrosis pulmonar', 'probabilidad_estimada': 0.78, 'threshold_usado': 0.5},
        {'etiqueta': 'Enfisema', 'probabilidad_estimada': 0.61, 'threshold_usado': 0.6},
    ]}
    assert 'Múltiples señales' in generar_texto_hallazgos(SimpleNamespace(patologias=data), 'PA')
    assert threshold_findings({'Fibrosis pulmonar': 0.99}) == []
