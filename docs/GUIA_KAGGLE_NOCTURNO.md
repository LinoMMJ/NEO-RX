# NeoRX: entrenamiento nocturno en Kaggle

Actualizado el 3 de noviembre de 2026. Este paquete entrena **ResNet-50 a 512 × 512**, con derrame pleural como hallazgo específico y cuatro salidas de orientación: tumoral, pleural, infecciosa e intersticial. El sistema local conserva el modelo v1 hasta que v2 supere la evaluación; este procedimiento no lo reemplaza automáticamente.

## 1. Archivos que debes usar

En la carpeta `entrega_kaggle` del proyecto encontrarás:

| Archivo | Uso |
| --- | --- |
| `NeoRX_Entrenamiento_Nocturno.ipynb` | Importar como notebook en Kaggle. |
| `neorx_kaggle_entrenamiento.zip` | Subir como un Dataset privado y agregar al notebook. Incluye código, pesos iniciales, metadatos NIH y la partición por paciente. |
| `GUIA_KAGGLE.md` | Esta guía. |
| `SHA256.json` | Huellas de los archivos para verificar que no se modificaron. |

El paquete no contiene la base de datos del sistema, contraseñas, `.env`, historias clínicas ni imágenes de pacientes del sistema. **Las 112.120 radiografías NIH no van dentro del ZIP**: debes agregarlas como otra entrada de Kaggle. No uses los notebooks antiguos focused3/focused5 para este entrenamiento.

## 2. Preparar las entradas en Kaggle

1. Inicia sesión en Kaggle con tu cuenta.
2. Crea un Dataset **privado** para el código y carga `neorx_kaggle_entrenamiento.zip`. Kaggle puede descomprimirlo: el notebook admite tanto el ZIP como su contenido extraído.
3. Crea un notebook e importa `NeoRX_Entrenamiento_Nocturno.ipynb` desde tu computadora. En el editor, la opción de importar está en el menú de archivos; los nombres pueden variar con el idioma de la interfaz.
4. En **Add Input / Add Data**, agrega el Dataset privado del código.
5. Agrega el dataset **NIH ChestX-ray14 completo**, el mismo utilizado anteriormente: `Data_Entry_2017.csv` y todos los grupos de imágenes, normalmente `images_001` a `images_012`. Una entrada de neumonía binaria, imágenes de ejemplo o un subconjunto no sirve para este paquete.
6. En la configuración del notebook, activa **GPU** e **Internet**. Las dependencias requieren Internet; los pesos iniciales ya están incluidos. No selecciones TPU. El código utiliza una GPU, aunque Kaggle ofrezca T4 ×2.
7. Comprueba la cuota y la duración máxima que Kaggle muestra para tu cuenta. Si GPU está deshabilitada, resuelve primero la verificación/cuota indicada por Kaggle; entrenar esta configuración en CPU no es una alternativa nocturna práctica.

## 3. Configuración de la primera noche

La primera celda de código contiene todos los parámetros que necesitas:

```python
MODE = "train"
DATA_ROOT = ""
PREVIOUS_OUTPUT = ""
SESSION_HOURS = 8
RESERVE_MINUTES = 45
BATCH_SIZE = 16
WORKERS = 2
```

Deja `DATA_ROOT` vacío si solo hay un archivo `Data_Entry_2017.csv` entre las entradas. Si la detección falla, copia la ruta de la carpeta NIH mostrada por el notebook, por ejemplo `/kaggle/input/datasets/autor/nih-chest-xrays`, **hasta la carpeta que contiene todos los grupos de imágenes**. Es un ejemplo: no copies una ruta que no exista en tu notebook.

`SESSION_HOURS = 8` es nuestro presupuesto solicitado, **no un límite oficial ni una garantía de Kaggle**. Reduce el valor si tu cuota o el límite de sesión disponible es menor. Debe superar el margen de reserva. La preparación consume parte del presupuesto; se dejan 45 minutos para finalizar y empaquetar. Una detención forzada por Kaggle, falta de espacio o agotamiento anticipado de cuota puede impedir guardar salidas: consulta los límites antes de lanzar.

Si la GPU se queda sin memoria, inicia una ejecución nueva con `BATCH_SIZE = 8`. Para continuar un entrenamiento ya iniciado, conserva su batch size y configuración. `WORKERS = 2` reduce presión de RAM; puedes usar 0 si falla la carga multiproceso, a costa de velocidad.

## 4. Dejarlo ejecutándose con la computadora apagada

1. Pulsa **Save Version**.
2. Elige **Save & Run All**, no solamente Quick Save.
3. Confirma que esa ejecución tiene GPU habilitada; revisa las opciones avanzadas si aparecen.
4. Guarda la versión y comprueba que su ejecución quedó iniciada.
5. Puedes cerrar el navegador o apagar tu computadora: esta modalidad ejecuta el notebook en una sesión de Kaggle independiente de la sesión interactiva.

No hace falta `nohup`, una terminal abierta ni mantener tu computadora encendida. Evita dejar otra sesión interactiva con GPU activa, porque también puede consumir cuota. Al usar Save & Run All, se ejecutan nuevamente todas las celdas desde el principio; las entradas deben estar adjuntadas y los parámetros guardados.

Referencia oficial: [Kaggle Notebooks](https://www.kaggle.com/docs/notebooks) y [uso eficiente de GPU](https://www.kaggle.com/docs/efficient-gpu-usage).

## 5. Qué hará automáticamente

1. Verificará la integridad del código y los pesos del paquete.
2. Comprobará que CUDA/GPU está disponible y registrará el entorno.
3. Leerá, decodificará y calculará la huella de las imágenes del dataset; registrará ausentes, corruptas, constantes y duplicadas. Verás mensajes cada 1.000 imágenes.
4. Conservará la partición de referencia por paciente. Verificará cobertura completa, ausencia de pacientes y contenidos compartidos entre particiones y etiquetas contradictorias. Si la limpieza cambia la cobertura, se detendrá y dejará un informe: no fabricará una partición nueva ni entrenará con un dataset incompleto.
5. Entrenará la cabeza de clasificación durante 3 épocas y después ajustará los últimos bloques durante un máximo de 24 épocas adicionales, con parada temprana.
6. Usará todos los ejemplos de las particiones, incluyendo negativos y hallazgos coexistentes. El equilibrio de clases se calcula exclusivamente con TRAIN.
7. Elegirá el mejor checkpoint por el **AUROC de la salida más débil** en VALIDACIÓN. Así una media alta o un buen derrame no pueden ocultar una categoría deficiente. Los umbrales y la habilitación de cada salida se ajustan con validación, nunca con TEST.
8. Guardará `best.pt`, `last.pt`, historial, estados de entrenamiento y un ZIP de resultados. Mostrará una estimación del tiempo restante después de completar una época.

**No se puede saber todavía si acabará en una noche.** Depende de GPU, almacenamiento, carga del servidor y parada temprana. La primera validación de los archivos también lleva tiempo. Si no termina, continúa desde el avance guardado la noche siguiente. Los tiempos del escaneo local no permiten calcular la duración del entrenamiento.

## 6. Interpretar la salida de la mañana siguiente

En la versión guardada abre **Output** y descarga `neorx_entrenamiento_resultados.zip`. Conserva también la versión en Kaggle: podrás adjuntar su salida a la próxima ejecución sin descargarla y volverla a subir.

| `neorx-run/STATUS.json` | Significado y siguiente paso |
| --- | --- |
| `paused_time_budget` | Avance guardado, falta entrenar. Continúa en otra versión. |
| `completed` | Terminó las épocas previstas. Ejecuta evaluación. |
| `early_stopped` | Terminó por falta de mejora en validación. Ejecuta evaluación. |
| `evaluated` | Evaluación terminada. Revisa métricas antes de instalar. |
| `preparation_only` | La preparación consumió el presupuesto. No empezó a entrenar. Ajusta el presupuesto dentro de tu cuota y lanza una ejecución nueva. |
| `failed` | Hubo un error. Consulta `console.log` y los informes; no lo interpretes como entrenamiento completado. |

Si Kaggle corta la sesión antes del empaquetado final, puede que no haya un ZIP actualizado. Usa la carpeta `neorx-run` guardada en Output si está disponible y verifica que contiene ambos checkpoints. No se garantiza recuperar archivos que Kaggle no haya persistido.

## 7. Reanudar otra noche

1. Abre una nueva edición/versión del mismo notebook.
2. Conserva las entradas de código y NIH.
3. Agrega como entrada la **salida de la versión anterior**. En Kaggle puedes buscar tus notebooks y seleccionar su versión con resultados. Si solo conservas el ZIP, súbelo como un Dataset privado y permite que Kaggle lo extraiga.
4. Localiza la carpeta que contiene `STATUS.json`, `config.runtime.yaml` y `checkpoints/`. El notebook imprime las carpetas anteriores que encuentra.
5. Cambia únicamente:

```python
MODE = "train"
PREVIOUS_OUTPUT = "/kaggle/input/.../neorx-run"  # sustituir por la ruta real
```

6. Mantén el batch size y los demás parámetros de aprendizaje de la ejecución original. Inicia nuevamente con **Save Version → Save & Run All**.

La reanudación restaura modelo, optimizador, planificador, AMP y estados aleatorios guardados. Conserva el mejor checkpoint anterior. **El guardado es por época completa**: si se interrumpe una época, esa época se repite. Con carga multiproceso, el estado interno de los trabajadores de aumentación no se conserva; no se promete una reproducción idéntica bit a bit.

Adjunta la carpeta completa; `last.pt` aislado no basta si el mejor resultado estaba en una época anterior. La preparación vuelve a comprobar los archivos originales y que los datos no cambiaron. No utilices checkpoints de los notebooks antiguos como reanudación: tienen otro contrato.

## 8. Evaluar cuando haya terminado

Después de `completed` o `early_stopped`, adjunta esa salida como en el paso anterior y cambia:

```python
MODE = "evaluate"
PREVIOUS_OUTPUT = "/kaggle/input/.../neorx-run"
```

Guarda una nueva versión con GPU. Esta ejecución utiliza los umbrales ya congelados, genera métricas, matrices y gráficos, y evalúa también la lógica real de derrame prioritario/categorías/abstención. No vuelve a entrenar.

Revisa especialmente:

- `evaluation/metrics.csv`: resultados por salida.
- `evaluation/routing_summary.json`: precisión, sensibilidad y frecuencia de resultados según lo que verá el usuario.
- `evaluation/metrics_by_view.csv`: comparación por proyección, cuando esté disponible.
- `evaluation/deployment_acceptance.json`: compuerta PASS/FAIL por cada salida.
- `runs/.../thresholds_validation.csv`: salidas que alcanzaron o no los criterios.
- `checkpoints/session_status.json` y `STATUS.json`: evidencia de finalización.

En VALIDACIÓN cada salida debe encontrar un umbral con sensibilidad ≥0,80 y especificidad ≥0,70, con soporte mínimo. En TEST la compuerta exige además AUROC ≥0,80 para **cada una** de las cinco salidas. **Son criterios de aceptación, no resultados obtenidos ni una promesa.** Si una salida no los alcanza, el informe indicará `do_not_deploy`; no se rebajan sus umbrales mirando TEST. Si cambias el modelo después de consultar TEST, necesitas otro conjunto independiente para una evaluación final válida.

Las cuatro categorías se derivan de etiquetas radiográficas, no de diagnósticos etiológicos confirmados. Además, los pesos preentrenados pueden haber visto imágenes NIH: esta partición separa pacientes durante nuestro ajuste fino, pero los resultados son una evaluación interna y no acreditan independencia respecto del preentrenamiento ni validación clínica externa.

## 9. Incorporar el modelo después de revisar sus resultados

Descarga el ZIP completo y conserva métricas, configuración y checkpoints. El candidato para el sistema será:

```text
neorx-run/checkpoints/neorx_effusion_categories_v2_resnet50.pt
```

No instales `last.pt` como modelo definitivo. No reemplaces el modelo temporal si el entrenamiento quedó pausado o no se evaluó. La integración posterior debe revisar los metadatos, las salidas habilitadas, la calidad del router y la latencia en tu computadora. ResNet-50 puede volver a ser más lenta que la DenseNet temporal, aunque mejore una métrica: se comprobarán ambas cosas antes del cambio.

La aplicación ya admite checkpoints con estas cinco salidas y sus umbrales. Cuando corresponda instalarlo, se conserva el respaldo del modelo actual, se configura `NEORX_MODEL_PATH` y se reinicia el backend. Este paquete solo prepara y ejecuta entrenamiento/evaluación; no modifica el sistema local.

## 10. Problemas frecuentes

| Mensaje o situación | Qué hacer |
| --- | --- |
| No encuentra el paquete | Agrega el Dataset privado del ZIP; deja una sola copia adjunta. |
| Varias entradas NIH | Define `DATA_ROOT` hasta la carpeta correcta. |
| `missing_file` | Falta parte del dataset o la ruta es incorrecta. Revisa `manifests/rejected_images.csv`. |
| Cambió la cobertura o hay duplicados | Revisa el informe antes de versionar otra partición; no desactives la comprobación. |
| CUDA no disponible | Activa GPU y comprueba cuota/verificación de cuenta. |
| `CUDA out of memory` | Nueva ejecución con batch 8; no reanudes cambiando silenciosamente el batch. |
| Configuración o dataset diferente al reanudar | Usa exactamente la misma versión de código, datos y parámetros, con la salida completa. |
| Se detuvo sin completar épocas | Lee `STATUS.json`; si hay `last.pt` válido, continúa la sesión. |
| Todas las salidas deshabilitadas | El experimento no alcanzó los objetivos. Eso requiere revisar datos/modelo, no inflar porcentajes. |

Referencia del modelo: [TorchXRayVision](https://github.com/mlmed/torchxrayvision). El código del paquete queda versionado con huellas SHA-256 en `bundle_manifest.json`.
