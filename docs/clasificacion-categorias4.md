# Clasificación jerárquica en cuatro categorías

> Diseño anterior. Desde el 23/10/2026 el nuevo flujo solicitado prioriza derrame pleural y atelectasia antes de recurrir a categorías. Véase [entrenamiento priority2](entrenamiento-priority2.md). Este documento describe el modo histórico, no el checkpoint nuevo.

Neo RX organiza la salida radiográfica en cuatro grupos:

- **Tumoral:** masa pulmonar y nódulo pulmonar.
- **Pleural:** derrame pleural, neumotórax y engrosamiento pleural.
- **Infecciosa:** neumonía, consolidación e infiltrado pulmonar. Son patrones compatibles; una radiografía no confirma el agente causal.
- **Intersticial:** fibrosis pulmonar y edema pulmonar.

La CNN conserva salidas por hallazgo porque más de un patrón puede coexistir. Después de aplicar los umbrales validados, una capa de decisión escoge una sola categoría principal únicamente cuando supera a la segunda por un margen mínimo. Si ninguna alcanza el criterio o dos categorías quedan próximas, el resultado es **no concluyente**.

El frontend y los informes muestran solamente las enfermedades pertenecientes a la categoría seleccionada. Las cifras se denominan puntuaciones del modelo y no porcentajes de certeza diagnóstica.

## Entrenamiento requerido

La configuración `backend/training/config.categories4.kaggle.yaml` entrena las diez etiquetas necesarias y exige umbrales con precisión, sensibilidad y soporte mínimos. El checkpoint actualmente instalado (`neorx_focused5_resnet50.pt`) no contiene todas las etiquetas ni una política de decisión validada; por seguridad, la nueva capa se abstiene con ese archivo.

Para habilitar las cuatro categorías se debe entrenar y evaluar `neorx_categories4_resnet50.pt`, copiarlo a `backend/models/` y configurar `NEORX_MODEL_PATH` con esa ruta. No se debe habilitar un checkpoint que no cumpla la validación independiente por paciente.
