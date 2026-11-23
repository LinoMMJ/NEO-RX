# Modelos de Neo RX

## Checkpoint de cinco salidas activo

El despliegue Docker utiliza `neorx_effusion_categories_resnet50.pt`, una
ResNet-50 ajustada a 512 px con derrame pleural como salida prioritaria y cuatro
salidas agregadas: tumoral, pleural, infecciosa e intersticial. Los pesos no se
modifican al cambiar el punto operativo.

Los umbrales seleccionados en VALIDACIÓN y configurados para el despliegue son:

- `Effusion`: 0,1676508635
- `CategoryTumoral`: 0,2112646401
- `CategoryPleural`: 0,1613885313
- `CategoryInfectious`: 0,1314414889
- `CategoryInterstitial`: 0,2572275996

La aplicación exige el conjunto completo mediante
`NEORX_DECISION_THRESHOLDS_JSON` y habilitación explícita mediante
`NEORX_ENABLE_THRESHOLD_DECISIONS=true`. Una configuración parcial detiene la
carga para evitar combinar umbrales antiguos y nuevos.

En TEST, estos puntos alcanzaron sensibilidades altas, pero especificidades y
precisiones bajas. Para derrame pleural: 94,30 % de sensibilidad, 54,00 % de
especificidad y 21,61 % de precisión. Por tanto, las salidas son señales para
revisión profesional y no validan uso clínico autónomo.

## Entrenamiento y validación futura

Un nuevo entrenamiento deberá respetar el mismo contrato: `Effusion` como única
salida específica y cuatro salidas de categoría, junto con una
`decision_policy` producida exclusivamente con validación. La configuración está
en `training/config.priority2.kaggle.yaml`; el nombre se conserva por
compatibilidad histórica aunque ahora existe una sola prioridad.

## Checkpoint focused5 existente (solo referencia)

El repositorio local puede cargar `neorx_focused5_resnet50.pt`, un modelo
ResNet-50 multietiqueta entrenado a 512 px para estas cinco categorías, en este
orden:

1. Emphysema — Enfisema
2. Edema — Edema pulmonar
3. Effusion — Derrame pleural
4. Mass — Masa pulmonar
5. Pneumothorax — Neumotórax

El checkpoint incluye los umbrales calculados con validación. No deben sustituirse
por un valor general de 0.5 sin volver a evaluar el modelo.

- Archivo: `neorx_focused5_resnet50.pt`
- Tamaño: 94.379.010 bytes
- SHA-256: `83A4DC0AC044651103DC1ACF8BEC5DA84AD3D7D53BD26E9824F38AF919C29070`
- Macro AUC del checkpoint seleccionado: 0,8271
- Macro average precision: 0,2468

Este checkpoint fue generado con el subconjunto piloto y no contiene la política
guardada de precisión/sensibilidad. La aplicación conserva sus puntuaciones para
auditoría, pero se abstiene de convertirlas en una conclusión clínica.

Los archivos `.pt` permanecen fuera de Git por su tamaño. Para desarrollo local,
la ruta se define en `backend/.env`; en Docker, el directorio se monta como solo
lectura en `/app/diagnostico/models`.

Este modelo produce señales de apoyo para revisión profesional; no confirma un
diagnóstico médico por sí solo.
