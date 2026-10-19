"""Compatibility adapter for legacy ES maps and structured CNN results."""
from numbers import Real
from math import isfinite


def threshold_findings(result):
    """Decisions require an acquisition-time threshold; never invent one."""
    if not isinstance(result, dict):
        return []
    rows = []
    for item in result.get('hallazgos', []):
        if not isinstance(item, dict):
            continue
        score, threshold = item.get('probabilidad_estimada'), item.get('threshold_usado')
        if not isinstance(score, Real) or not isinstance(threshold, Real):
            continue
        if not isfinite(score) or not isfinite(threshold) or not 0 <= score <= 1 or not 0 <= threshold <= 1:
            continue
        rows.append({**item, 'detectado': score >= threshold})
    return sorted(rows, key=lambda item: item['probabilidad_estimada'], reverse=True)


def probabilities_es(result):
    if not isinstance(result, dict):
        return {}
    if "hallazgos" in result:
        return {item["etiqueta"]: float(item["probabilidad_estimada"])
                for item in result["hallazgos"]
                if isinstance(item, dict) and isinstance(item.get("probabilidad_estimada"), Real)}
    return {key: float(value) for key, value in result.items() if isinstance(value, Real)}
