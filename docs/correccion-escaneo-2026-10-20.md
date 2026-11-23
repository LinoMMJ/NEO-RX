# Escaneo y correcciones relacionadas

## Evidencia

El registro local contiene una solicitud POST /api/estudios/upload/ de 79.541 segundos. El mapa del mismo recorrido respondió en 0.279 segundos. No se atribuye toda la duración de subida a la CNN sin una medición por etapas.

Se aplica NEORX_TORCH_THREADS también al reutilizar el singleton en nuevos hilos de solicitudes. El precalentamiento usa el mismo formato de memoria que la inferencia. Se conservan checkpoint, resolución 512, precisión numérica y política de decisión.

El benchmark sintético `python -m diagnostico.benchmark_threads` dio 13.991 segundos en el hilo principal y 11.090 / 10.896 en hilos nuevos. Las tres puntuaciones fueron idénticas entre ejecuciones. Es una comprobación técnica, no una prueba clínica ni una medición HTTP integral. Una medición anterior interrumpida dio 23.773 segundos en el hilo principal bajo otras condiciones de carga; no es una comparación controlada.

## Cambios

- PNG con compresión rápida sin pérdida; se evita la búsqueda costosa de compresión optimizada en cada subida.
- Celery utiliza el raster normalizado con orientación corregida, igual que la carga local.
- En desarrollo, la inferencia usa una cola interna de un solo trabajador. La API devuelve `202` inmediatamente y el frontend consulta el estado sin mantener abierta la subida durante varios minutos.
- Al reiniciar Django se recuperan automáticamente las radiografías válidas que quedaron pendientes, sin duplicar resultados.
- El estado del estudio cambia a `completado` tanto en la cola local/Celery como en el modo síncrono de respaldo.
- La pantalla termina la espera cuando Celery informa un fallo HTTP 500 o la sesión pierde autorización.
- Una respuesta tardía de vista previa DICOM no reemplaza la vista del archivo elegido después.
- Las estadísticas cuentan hallazgos aceptados por sus umbrales y política; se elimina el corte arbitrario de 15 %.
- El respaldo Redis consulta el estado real de BGSAVE, verifica éxito y limita la espera a 120 segundos.

## Verificación

- 83 pruebas backend de diagnóstico, regresiones, cargas y flujos operativos: aprobadas.
- 14 pruebas unitarias frontend: aprobadas.
- Build y lint frontend: aprobados.
- La primera ejecución de pruebas encontró restricciones de carpetas temporales; la repetición con permisos adecuados pasó.

Reiniciar Django y los workers para cargar el código. Recargar el frontend. Queda pendiente medir la subida HTTP completa en la sesión habitual y verificar el respaldo contra Redis real. No se entrenaron nuevos pesos ni se cerraron los pendientes de C4, gráficas, cifrado DICOM o conformidad SR durante esta corrección.
