# CRISP-DM Fase 6: Despliegue (Deployment)

## Integración con Django Backend

### 1. Checkpoint de Producción

```bash
# Copiar checkpoint final a ubicación accesible por Django
mkdir -p backend/diagnostico/models
cp checkpoints/finetuned_resnet50_nih.pt backend/diagnostico/models/
```

### 2. Variable de Entorno

```bash
# .env o docker-compose.yml
NEORX_MODEL_PATH=/app/diagnostico/models/finetuned_resnet50_nih.pt
```

**REGLAS CRÍTICAS:**
- Si `NEORX_MODEL_PATH` está configurado → **DEBE** existir el archivo
- **NO** hay fallback silencioso a baseline
- Error claro si archivo no existe

### 3. Carga del Modelo (Singleton)

`DetectorTorax.cargar()` — Patrón singleton, carga una vez:
```python
# Primera llamada:
if NEORX_MODEL_PATH configurado y existe:
    _cargar_finetuned()  # Carga checkpoint + thresholds
else:
    _cargar_baseline()   # Modelo preentrenado torchxrayvision

# Llamadas subsiguientes: retorna modelo ya cargado
```

### 4. Inferencia End-to-End

```
Usuario (Frontend)
    ↓
Sube DICOM/PNG → Django (UploadDICOMView)
    ↓
Celery Task (procesar_imagen_cnn)
    ↓
DetectorTorax.desde_dicom() / desde_png()
    ↓
predecir(img_array, maxval)
    ↓
Retorna:
{
    "hallazgos": [
        {"etiqueta": "Nódulo pulmonar", "etiqueta_en": "Nodule",
         "probabilidad_estimada": 0.82, "detectado": true, "threshold_usado": 0.35},
        ...
    ],
    "probabilidades": {"Nodule": 0.82, ...},
    "thresholds": {"Nodule": 0.35, ...},
    "modelo": "resnet50_finetuned_nih",
    "es_fine_tuned": true,
    "nota": "Resultado preliminar - requiere revisión profesional."
}
    ↓
Guardado en ResultadoCNN (JSONField)
    ↓
Frontend polling → ResultadoCNNView → Muestra en UI
```

### 5. Terminología en UI (Frontend)

**NUNCA usar:**
- "Diagnóstico confirmado"
- "El paciente tiene neumonía"
- "La IA diagnosticó..."

**USAR:**
- "Hallazgo detectado"
- "Probabilidad estimada"
- "Posible presencia"
- "Resultado preliminar"
- "Apoyo a la interpretación"
- "Requiere revisión profesional"

### 6. Niveles Visuales (UI) vs Thresholds Modelo

| Concepto | Origen | Propósito |
|----------|--------|-----------|
| **Threshold modelo** | Checkpoint (VALIDATION) | Decisión binaria detectado/no detectado |
| **Nivel visual** | `niveles.py` (configurable) | Codificación color: Alto/Moderado/Leve/Marginal |

**Independientes**: Un hallazgo puede estar "detectado" (prob > threshold_modelo) pero ser "Leve" en UI (prob < 0.40).

### 7. Grad-CAM (Interpretabilidad)

Endpoint: `GET /api/diagnostico/gradcam/?imagen_id=X&pathology=Nodule`

- Genera heatmap Grad-CAM sobre layer4 (última capa conv)
- Muestra regiones que influyeron en la predicción
- **Presentación**: "Visualización de regiones relevantes" — NO "prueba de que el modelo entendió"

### 8. Reinicio de Servicios

```bash
# Tras copiar checkpoint y configurar NEORX_MODEL_PATH
docker compose restart celery_worker
# o
systemctl restart neorx-celery
```

### 9. Verificación de Integración

Logs esperados:
```
INFO [DetectorTorax] Fine-tuned model loaded from /app/diagnostico/models/finetuned_resnet50_nih.pt
INFO [DetectorTorax] Classes: 12 | Thresholds loaded: 12
INFO [DetectorTorax] Thresholds: {'Atelectasis': 0.32, 'Consolidation': 0.41, ...}
```

Si aparece: `WARNING: No thresholds found in checkpoint, using 0.5 default` → Revisar entrenamiento.

### 10. Monitoreo en Producción

- **Métricas operativas**: Tiempo inferencia, throughput, errores
- **Drift detection**: Comparar distribución probabilidades vs entrenamiento
- **Feedback loop**: Radiólogos marcan FP/FN → dataset futuro

## Entregables de esta Fase

- [ ] Checkpoint copiado a `backend/diagnostico/models/`
- [ ] `NEORX_MODEL_PATH` configurado en entorno
- [ ] Celery worker reiniciado
- [ ] Test end-to-end: DICOM → predicción → UI
- [ ] Verificación: terminología correcta en frontend
- [ ] Verificación: Grad-CAM funcional
- [ ] Documentación de procedimiento de actualización de modelo
- [ ] Plan de monitoreo y feedback
