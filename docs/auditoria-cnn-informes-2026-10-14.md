# Revisión local del flujo CNN e informes — 14 de octubre de 2026

## Resultado y alcance

Se corrigieron y ejecutaron los recorridos de carga JPG y DICOM, previsualización, análisis con el checkpoint local de Kaggle, consulta de las 12 clases, mapas de calor, creación y edición del informe, firma y descarga PDF. La prueba integral empleó una base SQLite y archivos temporales con un paciente sintético; no creó informes de prueba en la base clínica.

El checkpoint no se reentrenó ni se cambiaron sus pesos. Los archivos del modelo y la configuración privada permanecen locales. Esta revisión comprueba funcionamiento del software; no establece sensibilidad, especificidad ni precisión clínica del modelo.

## Problemas corregidos

1. **Resolución incompatible:** el entorno local tenía `NEORX_INPUT_SIZE=224`, mientras el entrenamiento utilizó 512. Se restableció 512 y se ajustaron los hilos CPU a 4. La discrepancia modificaba considerablemente los scores: en una imagen de prueba, Mass pasó de 0,99414 a 0,38961 al usar la resolución del entrenamiento. Esto demuestra sensibilidad al preprocesamiento, no cuál es el diagnóstico correcto.
2. **Grad-CAM repetía cómputo:** para la arquitectura ResNet con pooling global y cabeza lineal se calcula el mismo mapa mediante sus pesos y las activaciones finales conservadas durante la inferencia. Una prueba lo compara con autograd. La caché en memoria es limitada; otros modelos conservan el recorrido con gradientes. Las solicitudes simultáneas se serializan y se vuelve a comprobar la caché.
3. **Mapa desalineado:** el overlay usa el mismo recorte central que la CNN. Su leyenda explica que representa influencia sobre el score y no un contorno de lesión.
4. **DICOM inconsistente:** vista previa, PNG, CNN y mapa comparten conversión de píxeles con LUT de modalidad/ventana e inversión MONOCHROME1. Se probó un DICOM con valores con signo y ventana, además del recorrido integral con DICOM sin comprimir.
5. **Imagen perdida o sustituida en informes:** cada informe nuevo fija `imagen_origen`; la interfaz, PDF y exportación usan esa referencia. Se conserva el acceso autenticado a imágenes JPG/PNG y DICOM convertido. La migración 0003 fue aplicada localmente después de un respaldo SQLite en `backend/.backups/`.
6. **Umbrales y metadatos descartados:** se conserva el resultado estructurado, con hallazgos, umbrales, resolución y advertencias. Los resultados antiguos siguen siendo legibles, identificados como históricos sin los metadatos faltantes.
7. **Presentación de certeza excesiva:** los scores ya no se redondean a «100%» ni se presentan como probabilidad clínica calibrada. Se muestran los umbrales del checkpoint y advertencias de saturación. Varias clases pueden tener scores altos porque la clasificación es multietiqueta. No se aplicaron factores arbitrarios ni softmax para ocultarlos.
8. **Flujo del informe:** visor ampliado con zoom y desplazamiento, mapa bajo demanda, aviso de cambios sin guardar y firma bloqueada mientras hay campos de plantilla pendientes o modificaciones sin guardar. Un tiempo de espera agotado conserva el estudio y lleva a consultar su estado, evitando repetir la carga.

## Mediciones reales

Checkpoint: `backend/models/finetuned_resnet50_nih.pt`; CPU local, 4 hilos, entrada 512×512. Carga inicial del modelo: **11,274 s**, una vez por proceso.

| Operación | JPG | DICOM |
| --- | ---: | ---: |
| Carga y procesamiento completo | 10,864 s | 10,161 s |
| Inferencia reportada | 10,718 s | 10,010 s |
| Primer mapa, reutilizando activaciones | 0,138 s | 0,128 s |
| Otra clase, reutilizando activaciones | 0,129 s | 0,146 s |
| Mapa servido desde caché | 0,005 s | 0,009 s |

Son observaciones de una imagen y su conversión a DICOM, con el modelo cargado y sin una prueba de concurrencia. Si las activaciones fueron expulsadas de memoria, se reinició el servidor o el mapa llega a otro proceso, necesita una pasada adicional de la CNN. No se garantiza el tiempo de caché para todos los estudios.

Evidencia local: `auditoria-flujo-2026-10-14.json` y `auditoria-informe-2026-10-14.jpg` (ignorados por Git).

## Validación ejecutada

- Suite completa del backend: 145 pruebas aprobadas antes de las últimas protecciones de Grad-CAM; la comprobación final de diagnóstico e informes aprobó 30 pruebas, incluyendo las dos nuevas protecciones.
- Frontend: 23 pruebas Vitest, 7 pruebas de sesión JWT y contraste de los 7 temas aprobados.
- ESLint y compilación de producción Vite aprobados después de los últimos ajustes de interfaz.
- Django: comprobación de configuración y ausencia de nuevas migraciones pendientes de generar.
- Recorrido integral sin simular la CNN: autenticación JWT, paciente, JPG, DICOM, preview, scores de 12 clases, cambio de clase del mapa y caché, imagen privada del informe, edición, firma y PDF.
- Navegador: tablero, lista de informes, informe firmado con radiografía visible, superposición de calor, cambio de patología y zoom de 100% a 125% y restablecimiento.
- Arranque normal verificado: frontend en 127.0.0.1:5173, backend en 127.0.0.1:8000, checkpoint fine-tuned con 12 clases y 12 umbrales, comprobaciones Django sin errores. La configuración local permite los orígenes localhost:5173 y 127.0.0.1:5173; preflight HTTP comprobado con respuesta 200. Los servidores temporales de prueba fueron detenidos.

## Reproducción

Desde `backend`, con el intérprete que tiene las dependencias instaladas:

```powershell
python manage.py migrate
python manage.py check
python -m diagnostico.audit_flow --image "ruta\a\radiografia.jpg"
```

`audit_flow` crea y elimina su propia base y medios temporales. Opcionalmente, `--serve` mantiene esa base de prueba en 127.0.0.1:8001; no es el servidor clínico. La prueba desactiva límites de tasa solo en ese proceso temporal para poder recorrer los endpoints.

Para el uso habitual local:

```powershell
# Terminal del backend
python manage.py runserver 127.0.0.1:8000 --noreload
# Otra terminal, en frontend
npm run dev -- --host 127.0.0.1
```

El `backend/venv` antiguo referencia una instalación de Python de otro usuario y no fue usado. Las pruebas se ejecutaron con el Python disponible del sistema y sus dependencias instaladas. No se reemplazó ni eliminó ese entorno antiguo.

## Límites y pendientes reales

- El AUC macro guardado en el checkpoint es aproximadamente 0,8158; no equivale a un 81,58% de aciertos ni demuestra calibración clínica. Falta evaluar con un conjunto independiente etiquetado, revisar errores por clase y calibrar con validación separada antes de afirmar mayor precisión.
- No se recalcularon estudios ni se modificaron textos de informes históricos. Para informes antiguos sin referencia explícita, la migración asocia la última imagen disponible del estudio; si existían varias, esa asociación requiere revisión documental.
- El filtro de imágenes raster usa heurísticas y no sustituye un clasificador anatómico validado. Tampoco se cubrieron todas las sintaxis DICOM comprimidas con archivos reales de la clínica.
- Docker/Celery/Redis no se certificaron en esta ejecución: el motor Docker no estaba disponible. La medición integral corresponde al modo local inline; el funcionamiento multiproceso y bajo carga requiere una prueba separada.
- No se realizó una auditoría exhaustiva de seguridad ni validación clínica. Los resultados funcionales anteriores no deben interpretarse como certificación para producción.
