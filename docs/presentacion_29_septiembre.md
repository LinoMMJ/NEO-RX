# Entrega del 29 de septiembre — NEO RX

## Alcance del cronograma

Para el 29 de septiembre se cierran el módulo de informes con IA y el módulo
de pacientes. También corresponde mostrar el inicio del módulo de análisis
radiográfico y el avance de cifrado y auditoría.

## Evidencia para la demostración

1. Iniciar sesión y mostrar los roles.
2. Crear o editar un paciente y abrir su historial.
3. Cargar una radiografía de tórax PNG o DICOM. El sistema valida el archivo,
   guarda el estudio, ejecuta la CNN y crea un borrador de informe.
4. Cargar una radiografía que no sea de tórax: se conserva como estudio
   registrado, pero no se envía a la CNN.
5. Mostrar el borrador de informe y el estado del estudio.
6. Mostrar la configuración de cifrado Fernet, JWT y el registro de auditoría.
7. Presentar las métricas experimentales del entrenamiento Kaggle: mejor
   macro-AUC de validación 0.8158; macro-AUC de prueba 0.8206 sobre 16,633
   estudios. Es apoyo experimental, no diagnóstico clínico autónomo.

## Conjunto de demostración de 600 estudios

Se crea solamente desde el `test` de NIH ChestX-ray14. El split tiene cero
imágenes compartidas con `train` y `val`; el generador selecciona una imagen
por paciente con semilla fija `60`.

Ejecutar en Kaggle, después de copiar `backend/training/create_demo_dataset.py`
de este proyecto al mismo checkout:

```bash
cd /kaggle/working/neorx/backend
python -m training.create_demo_dataset \
  --manifest /kaggle/working/manifests/clean_manifest.csv \
  --splits /kaggle/working/manifests/splits.json \
  --data-root /kaggle/input/datasets/nih-chest-xrays/data \
  --output-dir /kaggle/working/neorx_demo_600 \
  --count 600 --seed 60 --zip
```

El resultado incluye `images/`, `manifest.csv`, `splits.json`,
`dataset_card.json`, `README.md` y `neorx_demo_600.zip`. El manifiesto permite
pasar esas mismas 600 imágenes a una evaluación automática sin reentrenar.

Este conjunto es una muestra académica del dataset NIH, no un dataset propio
de la empresa. Para una futura validación clínica se requiere un conjunto
externo, con autorización y etiquetas revisadas por un radiólogo.
