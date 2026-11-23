# Clasificación jerárquica en cuatro categorías

> Flujo vigente: derrame pleural es la única salida específica prioritaria. Si no supera su umbral, el sistema intenta presentar una sola orientación entre cuatro categorías.

Neo RX organiza la salida radiográfica en cuatro grupos:

- **Tumoral:** masa pulmonar y nódulo pulmonar.
- **Pleural:** derrame pleural, neumotórax y engrosamiento pleural.
- **Infecciosa:** neumonía, consolidación e infiltrado pulmonar. Son patrones compatibles; una radiografía no confirma el agente causal.
- **Intersticial:** fibrosis pulmonar y edema pulmonar.

La CNN conserva salidas por hallazgo porque más de un patrón puede coexistir. Después de aplicar los umbrales validados, una capa de decisión escoge una sola categoría principal únicamente cuando supera a la segunda por un margen mínimo. Si ninguna alcanza el criterio o dos categorías quedan próximas, el resultado es **no concluyente**.

El frontend y los informes muestran solamente las enfermedades pertenecientes a la categoría seleccionada. Las cifras se denominan puntuaciones del modelo y no porcentajes de certeza diagnóstica.

## Checkpoint y punto operativo vigente

El checkpoint `neorx_effusion_categories_resnet50.pt` contiene las cinco salidas
del producto. Docker aplica los umbrales seleccionados en VALIDACIÓN mediante
`NEORX_DECISION_THRESHOLDS_JSON` y exige habilitación explícita con
`NEORX_ENABLE_THRESHOLD_DECISIONS=true`.

La evaluación TEST confirmó alta sensibilidad, pero también numerosas falsas
alertas. En las diez imágenes curadas de integración, el antiguo corte 0,99
activó alguna salida en 3 casos; los nuevos puntos lo hicieron en los 10. Esta
comparación demuestra el funcionamiento del umbral, no una mejora de exactitud.
Antes de uso clínico se requiere calibración, un conjunto independiente y
validación externa revisada por especialistas.
