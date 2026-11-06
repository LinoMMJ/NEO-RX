# Modelos de Neo RX

## ResNet-50 preentrenada activa

La configuración local actual usa `resnet50-res512-all` de TorchXRayVision sin
checkpoint propio. Presenta únicamente derrame pleural como hallazgo específico
y, en su ausencia, una categoría predominante. El punto operativo normalizado es 0,50. Este
modo no está calibrado con datos locales y no identifica tuberculosis.

Los pesos oficiales se almacenan en este directorio para que la demostración no
dependa de Internet. ResNet-50 trabaja a 512 px y tiene aproximadamente 25,5
millones de parámetros. En la CPU de demostración tarda aproximadamente 14–16
segundos por imagen después del precalentamiento.

## Entrenamiento futuro

El checkpoint futuro deberá respetar el mismo contrato de presentación del modo
temporal: `Effusion` como única salida específica y cuatro salidas de categoría,
junto con una `decision_policy` producida por validación. La configuración está
en `training/config.priority2.kaggle.yaml`; el nombre se conserva por compatibilidad
histórica aunque ahora existe una sola prioridad.

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
