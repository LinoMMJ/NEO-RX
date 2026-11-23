# Derrame pleural prioritario y orientación por categorías

Actualización del 24/10/2026: el sistema funciona temporalmente con la ResNet-50 preentrenada y muestra únicamente derrame pleural como hallazgo específico. El entrenamiento futuro debe conservar el mismo contrato: una salida prioritaria y cuatro categorías. Atelectasia ya no forma parte de la conclusión automática. No hay una precisión clínica nueva medida.

## Auditoría de los datos disponibles

Se analizaron `clean_manifest.csv` y `splits.json` de `results.zip`: 112.120 imágenes de 30.805 pacientes. La selección usa las frecuencias de TRAIN, no el rendimiento de TEST. Los recuentos son imágenes etiquetadas, no diagnósticos confirmados ni pacientes independientes.

| Hallazgo | Entrenamiento | Validación | Prueba | Total | Pacientes positivos únicos |
| --- | ---: | ---: | ---: | ---: | ---: |
| Infiltración | 13.997 | 2.912 | 2.985 | 19.894 | 8.035 |
| Derrame pleural | 9.400 | 1.968 | 1.949 | 13.317 | 4.275 |
| Atelectasia | 8.122 | 1.743 | 1.694 | 11.559 | 4.981 |

El análisis original señaló **derrame pleural y atelectasia** como los dos candidatos específicos con más soporte. Para reducir la ambigüedad solicitada, la versión operativa conserva únicamente **derrame pleural** en la conclusión. Infiltración es más numerosa, pero demasiado amplia para presentarla como enfermedad específica; se conserva para supervisar una categoría.

La auditoría comprueba cobertura exacta de las particiones, identificadores de imagen únicos, ausencia de pacientes compartidos, de hashes compartidos entre particiones y de etiquetas contradictorias `No Finding` + hallazgo. No sustituye una revisión médica de etiquetas, no detecta imágenes casi duplicadas y no elimina duplicados dentro de la misma partición. Los píxeles originales de Kaggle no están disponibles localmente: se deben revalidar antes del entrenamiento.

Informe completo local: `docs/auditoria-prioridades-2026-10-23.json`. Para reproducirlo desde `backend/`:

```powershell
python -m training.analyze_targets --archive ../results.zip --output ../docs/auditoria-prioridades-2026-10-23.json
```

## Qué cambia en el sistema

1. Una ResNet-50 compartida produce cinco salidas independientes: derrame pleural y cuatro categorías. No se usa softmax para forzar exclusividad.
2. Primero se aplican la política habilitada y el umbral del checkpoint a derrame pleural.
3. Si derrame pleural no cumple, se comparan las categorías habilitadas. Solo se muestra una cuando supera su umbral y se separa de la segunda por el margen configurado. Esto **no descarta** derrame pleural ni otras enfermedades.
4. Si hay empate, criterios insuficientes o pesos incompatibles, la respuesta es no concluyente o modelo pendiente de validación. Atelectasia no se presenta y no se fuerza dentro de una categoría incorrecta.
5. Frontend, informe y Grad-CAM consumen la decisión del backend. Los mapas corresponden a la salida específica seleccionada, incluida una categoría; no son una segmentación de lesión. La interfaz distingue puntuación de probabilidad diagnóstica.

Las categorías son agrupaciones experimentales derivadas de etiquetas NIH, no etiologías confirmadas:

| Salida | Etiquetas que la supervisan (unión lógica) |
| --- | --- |
| Tumoral | Mass, Nodule |
| Pleural | Effusion, Pneumothorax, Pleural_Thickening |
| Infecciosa | Pneumonia, Consolidation |
| Intersticial | Fibrosis, Edema, Infiltration |

Un nódulo no confirma tumor, la consolidación no confirma infección y los patrones agrupados como intersticiales pueden tener otras causas. Estas correspondencias necesitan revisión radiológica. Pueden coexistir varias categorías aunque se presente una orientación principal; las cuatro categorías no cubren toda enfermedad pulmonar.

## Entrenamiento en Kaggle

Utilizar el código actualizado de este proyecto, una GPU y el NIH completo. No reutilizar el notebook focused5 sin cambiar su configuración. Todos los comandos siguientes se ejecutan con `backend/` como directorio de trabajo (en un notebook, comandos de shell con `!`). No es necesario Docker.

1. Adjuntar el dataset original y `results.zip` como entradas. Instalar `training/requirements.kaggle.txt` en el entorno previsto. Verificar la ruta real del dataset: `/kaggle/input/datasets` es la raíz configurada por defecto; ajustarla si la entrada está en otra ruta. No apuntar el validador a varios datasets diferentes.
2. Revalidar los archivos y generar rutas vigentes; no reutilizar las rutas absolutas del manifiesto viejo:

```bash
python -m training.validate_dataset --input-root /kaggle/input/datasets --output-dir /kaggle/working/manifests-priority2 --workers 4
```

3. Conservar la partición original para poder comparar modelos. Ejecutar esta celda Python, cambiando solamente la ubicación real de `results.zip`. No extraer el ZIP completo: también contiene una copia del repositorio.

```python
import json
import zipfile
from pathlib import Path
from training.analyze_targets import analyze

archive_path = Path('/kaggle/input/TU-ENTRADA/results.zip')  # sustituir
folder = Path('/kaggle/working/manifests-priority2')
with zipfile.ZipFile(archive_path) as archive:
    splits = json.loads(archive.read('manifests-focused5/splits.json'))
manifest = (folder / 'clean_manifest.csv').read_text(encoding='utf-8-sig')
audit = analyze(manifest, splits)  # detiene el flujo si cambió la cobertura o existe fuga
assert audit['selected_targets'][0] == 'Effusion'
(folder / 'splits.json').write_text(json.dumps(splits), encoding='utf-8')
(folder / 'priority_audit.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
```

Si el validador excluye imágenes y la cobertura cambia, revisar el motivo y versionar una nueva partición por paciente antes de continuar; no omitir la comprobación. Conservar negativos y ejemplos con hallazgos coexistentes: entrenar solo positivos no permite distinguir derrame pleural del resto.

4. Entrenar y evaluar:

```bash
python -m training.train --config training/config.priority2.kaggle.yaml
python -m training.evaluate --config training/config.priority2.kaggle.yaml --checkpoint /kaggle/working/checkpoints-priority2/neorx_effusion_categories_resnet50.pt --output-dir /kaggle/working/evaluation-priority2
```

La selección del checkpoint prioriza el Average Precision de derrame pleural. Se mantienen cinco salidas para aprender la alternativa por categorías. La configuración exige en VALIDACIÓN precisión positiva ≥0,90, sensibilidad ≥0,60, al menos 30 predicciones y 100 positivos disponibles. **Son objetivos de selección, no resultados alcanzados ni garantías.** Cada salida que no los cumple se deshabilita; no se eleva artificialmente su porcentaje.

5. Revisar `metrics.csv`, `metrics_by_view.csv`, matrices y `routing_summary.json`. Este último aplica exactamente el router desplegado y mide precisión/sensibilidad efectivamente emitidas, uso de categorías y abstención. El acuerdo de categorías es contra etiquetas derivadas, no contra etiología confirmada. Los umbrales se congelan antes de TEST; no retocarlos mirando sus resultados. Si se modifica el modelo tras consultar TEST, reservar otro conjunto independiente.

Antes de afirmar mejoras, comparar con el modelo previo sobre los mismos pacientes, reportar intervalos de confianza agrupados por paciente, falsos negativos, falsos positivos y resultados AP/PA; revisar también un conjunto externo/local con etiquetas profesionales. El informe automático no calcula todavía intervalos por paciente ni valida datos externos. Más imágenes y menos clases no garantizan mejor precisión.

La separación por paciente auditada corresponde a este ajuste, no a la procedencia de los pesos base `resnet50-res512-all`. Hay que comprobar que el preentrenamiento no haya utilizado las imágenes de prueba; si no se puede demostrar, TEST no debe presentarse como totalmente independiente del modelo preentrenado. Reservar además evaluación externa no vista.

## Incorporar los pesos después de evaluarlos

Descargar y conservar checkpoint, configuración, auditorías y métricas. Copiar el checkpoint nuevo a `backend/models/` sin reemplazar el antiguo. En el `.env` que utiliza el backend configurar:

```dotenv
NEORX_DECISION_MODE=priority_category
NEORX_MODEL_PATH=models/neorx_effusion_categories_resnet50.pt
NEORX_INPUT_SIZE=512
```

Reiniciar el backend y los trabajadores. Verificar en una prueba de integración el nombre del modelo, seis etiquetas, `extra.config.decision_strategy`, umbrales y `decision_policy`. No activar manualmente salidas deshabilitadas para conseguir resultados visuales. Los estudios históricos conservan su resultado original; no se reclasifican sin un nuevo análisis explícito.

La integración del código no equivale a entrenamiento ni certificación. Hasta disponer del checkpoint nuevo evaluado, el sistema declara la limitación y no presenta el modelo anterior como especialista.
