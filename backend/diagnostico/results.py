"""Compatibility adapter for legacy ES maps and structured CNN results."""
from numbers import Real


def probabilities_es(result):
    if not isinstance(result, dict):
        return {}
    if "hallazgos" in result:
        return {item["etiqueta"]: float(item["probabilidad_estimada"])
                for item in result["hallazgos"]
                if isinstance(item, dict) and isinstance(item.get("probabilidad_estimada"), Real)}
    return {key: float(value) for key, value in result.items() if isinstance(value, Real)}
