"""Compatibility adapter for legacy ES maps and structured CNN results."""
from numbers import Real
from math import isfinite


def threshold_findings(result):
    """Decisions require an acquisition-time threshold; never invent one."""
    if not isinstance(result, dict):
        return []
    if result.get('enfoque'):
        return list(result['enfoque'].get('hallazgos_detectados', []))
    rows = []
    category = result.get("categoria") if isinstance(result.get("categoria"), dict) else None
    selected_category = category.get("clave") if category and category.get("estado") == "seleccionada" else None
    # New hierarchical results contribute to reports only from the selected
    # category. Ambiguous/abstained results must not leak competing findings.
    if category and not selected_category:
        return []
    for item in result.get('hallazgos', []):
        if not isinstance(item, dict):
            continue
        if selected_category and item.get("categoria") != selected_category:
            continue
        score, threshold = item.get('probabilidad_estimada'), item.get('threshold_usado')
        if not isinstance(score, Real) or not isinstance(threshold, Real):
            continue
        if not isfinite(score) or not isfinite(threshold) or not 0 <= score <= 1 or not 0 <= threshold <= 1:
            continue
        decision_enabled = item.get('decision_habilitada')
        detected = score >= threshold if decision_enabled is not False else False
        rows.append({**item, 'detectado': detected})
    return sorted(rows, key=lambda item: item['probabilidad_estimada'], reverse=True)


def probabilities_es(result):
    if not isinstance(result, dict):
        return {}
    if result.get('enfoque'):
        return {row['etiqueta']: float(row['probabilidad_estimada'])
                for row in result['enfoque'].get('hallazgos_detectados', [])}
    if "hallazgos" in result:
        category = result.get("categoria") if isinstance(result.get("categoria"), dict) else None
        selected_category = category.get("clave") if category and category.get("estado") == "seleccionada" else None
        if category and not selected_category:
            return {}
        return {item["etiqueta"]: float(item["probabilidad_estimada"])
                for item in result["hallazgos"]
                if isinstance(item, dict)
                and isinstance(item.get("probabilidad_estimada"), Real)
                and (not selected_category or item.get("categoria") == selected_category)}
    return {key: float(value) for key, value in result.items() if isinstance(value, Real)}
