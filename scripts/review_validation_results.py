"""Audit saved validation predictions; do not train, infer or change deployment."""
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from training.analyze_validation import dataset_identity, operating_points
from diagnostico.priority_policy import expanded_labels


def main():
    source = ROOT / 'neorx_validacion_sensibilidad.zip'
    destination = ROOT / 'entrega_kaggle/revision_validacion_sensibilidad'
    evidence = destination / 'evidencia'
    evidence.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as archive:
        assert archive.testzip() is None, 'Corrupt ZIP'
        base = 'neorx-validation-analysis/'
        def read(name):
            return archive.read(base+name)
        provenance = json.loads(read('provenance.json'))
        assert json.loads(read('STATUS.json'))['status'] == 'validation_analysis_complete'
        saved = np.load(io.BytesIO(read('validation_predictions.npz')), allow_pickle=False)
        targets, scores, ids, labels = (saved[k] for k in ('targets', 'probabilities', 'image_ids', 'labels'))
        assert targets.shape == scores.shape == (16673, 5)
        assert len(set(ids)) == len(ids) == 16673
        assert np.isfinite(scores).all() and ((scores >= 0) & (scores <= 1)).all()
        comparisons = list(csv.DictReader(io.StringIO(read('comparacion_sensibilidad.csv').decode())))
        discrimination = list(csv.DictReader(io.StringIO(read('discriminacion_VALIDACION.csv').decode())))
        baseline = list(csv.DictReader(io.StringIO(read('umbrales_originales_VALIDACION.csv').decode())))
        for name in ['STATUS.json', 'provenance.json', 'comparacion_sensibilidad.csv',
                     'discriminacion_VALIDACION.csv', 'umbrales_originales_VALIDACION.csv',
                     'sensibilidad_falsas_alarmas.png', 'pip_check.txt', 'LEEME.txt']:
            (evidence / name).write_bytes(read(name))
        # Cross-check the human-readable prediction CSV with the binary archive.
        exported = list(csv.DictReader(io.StringIO(read('validation_predictions.csv').decode())))
        assert [r['image_id'] for r in exported] == ids.tolist()
        for j, label in enumerate(labels):
            np.testing.assert_array_equal([float(r[f'{label}_target']) for r in exported], targets[:, j])
            np.testing.assert_allclose([float(r[f'{label}_score']) for r in exported], scores[:, j], rtol=0, atol=0)
        # Verify every full threshold curve, including tied scores.
        curves = {}
        for j, label in enumerate(labels):
            points = operating_points(targets[:, j], scores[:, j])
            stored = list(csv.DictReader(io.StringIO(read(f'thresholds_{label}.csv').decode())))
            assert len(stored) == len(points)
            for expected, actual in zip(points, stored):
                for key, value in expected.items():
                    assert abs(value-float(actual[key])) < 1e-10, (label, key)
            curves[str(label)] = points
    with zipfile.ZipFile(ROOT / 'neorx_entrenamiento_resultados.zip') as original:
        base = 'neorx-evaluation/'
        frozen = json.loads(original.read(base+'FREEZE.json'))
        assert provenance['checkpoint_sha256'] == frozen['checkpoint_sha256']
        manifest_text = original.read(base+'manifests/clean_manifest.csv').decode('utf-8-sig')
        splits = json.loads(original.read(base+'manifests/splits.json'))
        assert dataset_identity(manifest_text, splits) == provenance['dataset_identity']
        assert ids.tolist() == splits['val']
        assert not set(ids).intersection(splits['test'])
        rows = {r['Image Index']: r for r in csv.DictReader(io.StringIO(manifest_text))}
        expected_targets = [[int(label in expanded_labels(rows[name]['Finding Labels'])) for label in labels] for name in ids]
        np.testing.assert_array_equal(targets, expected_targets)
        val_patients = {rows[name]['Patient ID'] for name in ids}
        assert all(not val_patients.intersection({rows[name]['Patient ID'] for name in splits[part]})
                   for part in ('train', 'test'))
    for row in comparisons + baseline:
        j = labels.tolist().index(row['label'])
        prediction = scores[:, j] >= float(row['threshold'])
        positive = targets[:, j] == 1
        counts = dict(tp=int((prediction & positive).sum()), fp=int((prediction & ~positive).sum()),
                      fn=int((~prediction & positive).sum()), tn=int((~prediction & ~positive).sum()))
        assert all(int(row[k]) == v for k, v in counts.items())
    checks = []
    for j, label in enumerate(labels):
        reported = next(r for r in discrimination if r['label'] == label)
        auc, ap = roc_auc_score(targets[:, j], scores[:, j]), average_precision_score(targets[:, j], scores[:, j])
        assert abs(auc-float(reported['auc'])) < 1e-10
        assert abs(ap-float(reported['average_precision'])) < 1e-10
        eligible = [p for p in curves[str(label)] if .05 <= p['threshold'] <= .99 and p['tp']+p['fp'] >= 30]
        meets_original = [p for p in eligible if p['sensitivity'] >= .6 and p['precision'] >= .9]
        checks.append(dict(label=str(label), positive_support=int(targets[:, j].sum()),
                           auc=float(auc), ap=float(ap), meets_original_criteria=bool(meets_original),
                           maximum_precision_at_sensitivity_at_least_80=max(p['precision'] for p in eligible if p['sensitivity'] >= .8),
                           auc_delta_from_training=float(auc-provenance['validation_metrics_at_training']['per_class_auc'][j]),
                           ap_delta_from_training=float(ap-provenance['validation_metrics_at_training']['per_class_average_precision'][j])))
    report = dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), samples=len(ids),
                  positive_effusion=1968, negative_effusion=14705, validation_patients=len(val_patients),
                  checkpoint_matches_reviewed_test=True, exact_validation_ids_and_labels=True,
                  patient_overlap_train_or_test=0, csv_matches_npz=True, all_threshold_curves_recomputed=True,
                  confusion_counts_and_auc_ap_recomputed=True, deployment_changed=False,
                  checks=checks, limitation='Saved predictions verified, no local pixel access or new inference. Validation used for model selection; not independent clinical validation.')
    (destination / 'VERIFICACION.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    lines = ['# Revisión del análisis de VALIDACIÓN de NeoRX', '',
             'El archivo está íntegro. Se comprobaron las 16.673 predicciones, las etiquetas, los pacientes, '
             'la identidad del modelo, las curvas completas de umbrales, las matrices de confusión y AUC/AP. '
             'Las imágenes corresponden exactamente a VALIDACIÓN, con 4.620 pacientes sin solapamiento con TRAIN/TEST.', '',
             '## Derrame pleural', '',
             'VALIDACIÓN contiene 1.968 imágenes positivas y 14.705 negativas para derrame. '
             'Son etiquetas del dataset NIH. El TEST anterior tenía otra composición; sus cifras no deben mezclarse.', '',
             '| Sensibilidad | Umbral (aprox.) | TP | FN | FP | TN | Precisión (VPP) | FP / 1.000 negativos |',
             '|---|---|---|---|---|---|---|---|']
    for row in [r for r in baseline+comparisons if r['label'] == 'Effusion']:
        fp_rate = int(row['fp']) / (int(row['fp'])+int(row['tn'])) * 1000
        lines.append(f"| {float(row['sensitivity'])*100:.2f}% | {float(row['threshold']):.6f} | {row['tp']} | {row['fn']} | {row['fp']} | {row['tn']} | {float(row['precision'])*100:.2f}% | {fp_rate:.1f} |")
    lines += ['', 'Los umbrales mostrados están redondeados solo para lectura. El cálculo usa los valores exactos del CSV.', '',
              'A sensibilidad 80,03%, 1.575 alertas coinciden con etiquetas positivas y 2.803 son falsas alarmas; '
              '393 positivos quedan sin detectar. La precisión es 35,98%: aproximadamente 36 de cada 100 alertas '
              'son verdaderas según estas etiquetas. No significa 80% de acierto general ni confirma eficacia clínica.', '',
              'A sensibilidad 90,04%, detecta 1.772 positivos, omite 196 y produce 4.933 falsas alarmas '
              '(precisión 26,43%). Aumentar sensibilidad no elimina la ambigüedad.', '',
              '## Categorías al escenario cercano a 80% de sensibilidad', '',
              '| Clase | Sensibilidad | Precisión (VPP) | FP / 1.000 negativos |', '|---|---|---|---|']
    for row in comparisons:
        if row['label'] != 'Effusion' and float(row['sensitivity_target']) == .8:
            lines.append(f"| {row['label']} | {float(row['sensitivity'])*100:.2f}% | {float(row['precision'])*100:.2f}% | {float(row['false_positives_per_1000_negatives']):.1f} |")
    lines += ['', 'Son resultados binarios por clase. No representan el desempeño del flujo que elige primero derrame '
              'y luego una sola categoría. La categoría pleural incluye derrame; no es una segunda confirmación independiente.', '',
              '## Interpretación y alcance', '',
              '- Ninguna de las cinco salidas cumple el criterio original conjunto de precisión >=90% y sensibilidad >=60%, '
              'con umbral 0,05–0,99 y al menos 30 predicciones positivas. Se comprobó la curva completa, no solo cuatro filas.',
              '- AUC de derrame = 0,88051 y AP = 0,52259: hay capacidad de ordenar positivos frente a negativos, '
              'pero AUC no equivale a porcentaje de diagnósticos correctos.',
              '- Respecto al entrenamiento, las diferencias de AUC son menores de 0,00006 y de AP menores de 0,00064. '
              'Al umbral 0,99 hay 34 TP y 8 FP, frente a 34 TP y 7 FP registrados durante entrenamiento. '
              'La validación del entrenamiento usaba precisión mixta y este análisis inferencia sin autocast; '
              'esa diferencia es compatible con variación numérica, sin demostrar su causa. No explica el problema de sensibilidad.',
              '- La revisión no modifica pesos, umbrales ni configuración del sistema. No hace falta repetir esta ejecución '
              'para seguir examinando los scores guardados.',
              '- Ajustar un umbral modifica decisiones, no mejora la separación aprendida por el modelo. '
              'No hay base para prometer que más épocas o un modelo preentrenado alternativo será mejor sin comparación.',
              '- Para la tesis, reportar el modelo como prototipo experimental y separar los resultados de TEST con política '
              'original de esta exploración posterior de VALIDACIÓN. Una política revisada necesita evaluación independiente; '
              'no utilizar TEST ya consultado para escogerla.', '',
              'Referencias: [precision–recall, scikit-learn](https://scikit-learn.org/stable/auto_examples/model_selection/plot_precision_recall.html) '
              'y [ajuste de umbrales](https://scikit-learn.org/stable/modules/classification_threshold.html).', '',
              'Limitación de esta revisión local: se verificaron artefactos guardados; no se volvieron a abrir las radiografías NIH ni se ejecutó inferencia.']
    (destination / 'REVISION.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
