# Umbrales desplegados en NeoRX — 22 de noviembre de 2026

## Configuración activa

| Salida | Umbral | Sensibilidad TEST | Especificidad TEST | Precisión TEST |
|---|---:|---:|---:|---:|
| Derrame pleural | 0,167651 | 94,30 % | 54,00 % | 21,61 % |
| Tumoral | 0,211265 | 95,53 % | 24,80 % | 12,62 % |
| Pleural | 0,161389 | 93,46 % | 45,78 % | 26,99 % |
| Infecciosa | 0,131441 | 94,22 % | 37,00 % | 8,12 % |
| Intersticial | 0,257228 | 95,61 % | 18,70 % | 23,42 % |

Los umbrales fueron seleccionados en VALIDACIÓN y aplicados sin reajuste a TEST.
Cambian la decisión binaria, pero no los pesos ni las puntuaciones producidas por
la red.

## Comprobaciones realizadas

- El contenedor cargó `neorx_effusion_categories_v1` a 512 px.
- Las cinco políticas quedaron habilitadas con estado
  `validation_operating_point_selected`.
- Las 11 pruebas unitarias específicas de la configuración aprobaron.
- La regresión del módulo diagnóstico aprobó; dos pruebas del pipeline de
  entrenamiento se omitieron en la imagen de producción porque `scikit-learn`
  pertenece al entorno de Kaggle.
- Frontend: 46 pruebas unitarias, 7 pruebas de sesión y 7 verificaciones de
  contraste aprobaron.
- Playwright: 11 de 11 pruebas funcionales aprobaron, incluido el flujo de
  carga, inferencia, puntuación, Grad-CAM y apertura del informe.

## Comparación sobre las muestras guardadas

Con el corte anterior 0,99, 3 de 10 imágenes activaron al menos una salida. Con
los nuevos umbrales, 10 de 10 activaron al menos una salida. Varias imágenes
activaron más de una categoría y algunas placas no etiquetadas como derrame
superaron el umbral de `Effusion`.

Este comportamiento coincide con la matriz de TEST: aumenta la recuperación de
positivos, pero conserva baja precisión y especificidad. Las muestras son
curadas y no permiten estimar exactitud clínica. No deben usarse para volver a
ajustar los umbrales.
