"""Versioned two-finding specialist with a separately trained category fallback.

All outputs remain multi-label: a low score does not establish absence, and
coexisting primary findings are never forced into an exclusive diagnosis.
"""
import math

STRATEGY = 'priority_then_category_v1'
PRIMARY_LABELS = ['Effusion', 'Atelectasis']
CATEGORY_HEADS = {
    'CategoryTumoral': ('tumoral', 'Tumoral', ['Mass', 'Nodule']),
    'CategoryPleural': ('pleural', 'Pleural', ['Effusion', 'Pneumothorax', 'Pleural_Thickening']),
    'CategoryInfectious': ('infecciosa', 'Infecciosa', ['Pneumonia', 'Consolidation']),
    'CategoryInterstitial': ('intersticial', 'Intersticial', ['Fibrosis', 'Edema', 'Infiltration']),
}
SPECIFIC_CANDIDATES = ['Effusion', 'Atelectasis', 'Nodule', 'Mass', 'Pneumothorax',
                       'Pleural_Thickening', 'Emphysema', 'Edema', 'Fibrosis', 'Pneumonia']


def expanded_labels(raw):
    labels = set(filter(None, (value.strip() for value in str(raw).split('|'))))
    return labels | {head for head, (_, _, members) in CATEGORY_HEADS.items() if labels.intersection(members)}


def priority_result(scores, thresholds, policies, names, strategy=None):
    strategy = strategy if isinstance(strategy, dict) else {}
    primary = strategy.get('primary_labels', PRIMARY_LABELS)
    if not isinstance(primary, list) or not all(isinstance(label, str) for label in primary):
        primary = []
    compatible = (strategy.get('type') == STRATEGY and isinstance(primary, list)
                  and 1 <= len(primary) <= 2 and len(set(primary)) == len(primary)
                  and set(primary).issubset(SPECIFIC_CANDIDATES)
                  and set([*primary, *CATEGORY_HEADS]).issubset(scores))
    findings = []
    for label in [*primary, *CATEGORY_HEADS]:
        score, threshold = scores.get(label), thresholds.get(label)
        if not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
            continue
        valid_threshold = isinstance(threshold, (int, float)) and math.isfinite(threshold) and 0 <= threshold <= 1
        enabled = bool(compatible and valid_threshold and policies.get(label, {}).get('enabled') is True)
        findings.append({
            'etiqueta_en': label, 'etiqueta': names.get(label, label),
            'probabilidad_estimada': score, 'threshold_usado': threshold if valid_threshold else None,
            'decision_habilitada': enabled, 'detectado': enabled and score >= threshold,
            'tipo_salida': 'prioritaria' if label in primary else 'categoria',
        })
    detected = sorted([row for row in findings if row['tipo_salida'] == 'prioritaria' and row['detectado']],
                      key=lambda row: row['probabilidad_estimada'], reverse=True)
    category = {'estado': 'no_concluyente', 'clave': None, 'nombre': 'No concluyente', 'enfermedades': []}
    enabled = [row for row in findings if row['decision_habilitada']]
    state, title = 'no_concluyente', 'Resultado no concluyente'
    gradcam_targets = []
    message = 'No se alcanzaron criterios validados. Esto no confirma ni descarta enfermedad.'
    if not compatible or not enabled:
        state = 'modelo_pendiente_validacion'
        message = 'Se requiere el nuevo checkpoint de hallazgos prioritarios y categorías con decisiones validadas. El modelo instalado no acredita este flujo.'
    elif detected:
        gradcam_targets = [{'etiqueta_en': row['etiqueta_en'], 'etiqueta': row['etiqueta']} for row in detected]
        state, title = 'hallazgos_prioritarios', 'Hallazgos prioritarios para revisión'
        message = 'Señales compatibles con ' + ', '.join(row['etiqueta'].lower() for row in detected) + '. Requieren confirmación profesional; pueden coexistir otros hallazgos.'
    else:
        groups = []
        for row in findings:
            if row['tipo_salida'] == 'categoria' and row['detectado']:
                evidence = (row['probabilidad_estimada'] - row['threshold_usado']) / max(row['threshold_usado'], 1e-6)
                if evidence > 0:
                    groups.append((evidence, row))
        groups.sort(key=lambda item: item[0], reverse=True)
        margin = groups[0][0] - groups[1][0] if len(groups) > 1 else None
        minimum_margin = float(strategy.get('category_margin', 0.10))
        if not math.isfinite(minimum_margin) or minimum_margin < 0:
            raise ValueError('Invalid category margin')
        if groups and (margin is None or margin >= minimum_margin):
            _, row = groups[0]
            key, name, _ = CATEGORY_HEADS[row['etiqueta_en']]
            state, title = 'orientacion_categoria', f'Orientación por categoría: {name}'
            message = 'No se confirmó un hallazgo prioritario con los criterios del modelo. Se ofrece orientación por categoría; no significa que los hallazgos prioritarios estén ausentes.'
            category.update(estado='seleccionada', clave=key, nombre=name, mensaje=message)
            gradcam_targets = [{'etiqueta_en': row['etiqueta_en'], 'etiqueta': f'Orientación {name.lower()}'}]
        elif groups:
            message = 'Las categorías tienen evidencia cercana. Se requiere revisión de la imagen; no se fuerza una categoría.'
    category.setdefault('mensaje', message)
    return {
        'enfoque': {'version': STRATEGY, 'estado': state, 'prioritarias': list(primary),
                    'hallazgos_detectados': detected, 'checkpoint_compatible': compatible,
                    'objetivos_gradcam': gradcam_targets},
        'decision': {'estado': state, 'titulo': title, 'mensaje': message,
                     'hallazgos_principales': [row['etiqueta'] for row in detected]},
        'categoria': category, 'hallazgos': findings,
        'alcance': [names.get(label, label) for label in primary],
        'probabilidades': {row['etiqueta_en']: row['probabilidad_estimada'] for row in findings},
        'thresholds': {row['etiqueta_en']: row['threshold_usado'] for row in findings},
    }


def add_experimental_orientation(result, scores, names, minimum_score=0.50, category_margin=0.08):
    """Add a clearly labelled demo orientation without enabling clinical policy.

    This never changes thresholds, ``decision_habilitada`` or ``detectado``.
    It exists only for academic demonstration while a validated checkpoint is
    unavailable and must be activated explicitly by the deployment.
    """
    if result.get('enfoque', {}).get('estado') not in {
        'modelo_pendiente_validacion', 'no_concluyente'
    }:
        return result
    if not 0 <= minimum_score <= 1 or not 0 <= category_margin <= 1:
        raise ValueError('Invalid experimental orientation settings')

    effusion = scores.get('Effusion')
    if isinstance(effusion, (int, float)) and math.isfinite(effusion) and effusion >= minimum_score:
        label = names.get('Effusion', 'Derrame pleural')
        result['enfoque'].update(
            estado='hallazgo_prioritario_experimental', modo='demostracion_no_validada',
            objetivos_gradcam=[{'etiqueta_en': 'Effusion', 'etiqueta': label}],
        )
        result['decision'] = {
            'estado': 'hallazgo_prioritario_experimental',
            'titulo': f'Señal experimental compatible con {label.lower()}',
            'mensaje': 'Orientación técnica para demostración académica. No utiliza un umbral clínico validado y requiere revisión profesional.',
            'hallazgos_principales': [label],
        }
        result['demostracion'] = {
            'activa': True, 'validada': False, 'etiqueta_en': 'Effusion',
            'etiqueta': label, 'puntuacion_tecnica': float(effusion),
        }
        return result

    ranked = []
    for head, (key, name, _) in CATEGORY_HEADS.items():
        score = scores.get(head)
        if isinstance(score, (int, float)) and math.isfinite(score):
            ranked.append((float(score), head, key, name))
    ranked.sort(reverse=True)
    if not ranked or ranked[0][0] < minimum_score:
        return result
    margin = ranked[0][0] - ranked[1][0] if len(ranked) > 1 else 1.0
    if margin < category_margin:
        return result

    score, head, key, name = ranked[0]
    message = (
        'Categoría técnica predominante para demostración académica. '
        'No es una decisión clínica validada ni un porcentaje de certeza diagnóstica.'
    )
    result['enfoque'].update(
        estado='orientacion_categoria_experimental', modo='demostracion_no_validada',
        objetivos_gradcam=[{'etiqueta_en': head, 'etiqueta': f'Orientación {name.lower()}'}],
    )
    result['decision'] = {
        'estado': 'orientacion_categoria_experimental',
        'titulo': f'Orientación experimental: {name}',
        'mensaje': message,
        'hallazgos_principales': [],
    }
    result['categoria'].update(
        estado='seleccionada', clave=key, nombre=name, mensaje=message,
        validada=False, puntuacion_tecnica=score,
    )
    result['demostracion'] = {
        'activa': True, 'validada': False, 'etiqueta_en': head,
        'etiqueta': f'Orientación {name.lower()}', 'puntuacion_tecnica': score,
        'margen_tecnico': margin,
    }
    return result
