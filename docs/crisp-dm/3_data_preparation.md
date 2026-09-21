# CRISP-DM Fase 3: Preparación de los Datos (Data Preparation)

## Pipeline de Preparación

```bash
python -m training.prepare_dataset \
  --data-dir data/nih \
  --source local \
  --labels pulmonary \
  --seed 42
```

## Pasos Implementados

### 1. Validación de Estructura Local
- Verifica existencia de `data/nih/images/` y `data/nih/Data_Entry_2017.csv`
- Cuenta imágenes (PNG/JPG)
- Valida columnas requeridas en CSV

### 2. Parseo de Etiquetas Multi-label
```python
# "Atelectasis|Consolidation|No Finding" → ["Atelectasis", "Consolidation"]
# Filtrado: solo etiquetas en label_set (12 clases pulmonares)
```

### 3. División Patient-Level (CRÍTICO - Sin Data Leakage)
```python
# 1. Obtener pacientes únicos
patients = df["Patient ID"].unique()

# 2. Split pacientes (no imágenes!)
train_patients, temp_patients = train_test_split(patients, train_size=0.7, random_state=42)
val_patients, test_patients = train_test_split(temp_patients, train_size=0.5, random_state=42)

# 3. Mapear imágenes a splits vía Patient ID
# 4. VALIDACIÓN AUTOMÁTICA: validate_patient_overlap() → FALLA si overlap > 0
```

**Ratios**: Train 70% / Validation 15% / Test 15%

### 4. Generación de Estadísticas
- `dataset_statistics.csv`: Distribución por clase + por split
- `dataset_summary.json`: Metadatos completos del dataset
- `labels.json`: Lista de etiquetas usadas
- `splits.json`: Índices de train/val/test para reproducibilidad

### 5. Subsampling Opcional (Para Pruebas de Pipeline)
```bash
--max-samples 2000 --stratify --seed 42
```
- Mantiene patient-level integrity
- Balancea clases aproximadamente
- **SOLO para verificación técnica** — NO para resultados finales

## Data Augmentation (Solo TRAIN)

Configurado en `config.yaml`:

```yaml
augmentation:
  enabled: true
  rotation_degrees: 5        # ±5°
  scale_range: 0.10          # ±10% escala
  brightness: 0.15           # ±15% brillo
  contrast: 0.15             # ±15% contraste
  gaussian_noise_std: 0.01   # Ruido gaussiano
  horizontal_flip: false     # NO flip (lateralidad anatómica)
```

**VALIDATION y TEST**: Solo preprocesamiento (CenterCrop + Resize 512)

## Preprocesamiento (Todos los Splits)

```python
# 1. Cargar imagen → grayscale (L)
# 2. Normalize xrv: maxval=255 → rango [-1024, 1024]
# 3. CenterCrop (elimina bordes)
# 4. Resize 512x512
# 5. Tensor [1, 512, 512]
```

## Manejo de Desbalance de Clases

**pos_weight en BCEWithLogitsLoss** (calculado SOLO desde TRAIN):

```python
pos_weight[c] = n_negative[c] / n_positive[c]  # por clase
```

- Calculado en `train.py` al iniciar entrenamiento
- Guardado en checkpoint para reproducibilidad
- NO usa VALIDATION ni TEST

## Archivos Generados

| Archivo | Descripción |
|---------|-------------|
| `data/nih/splits.json` | Índices train/val/test (patient-level) |
| `data/nih/dataset_statistics.csv` | Distribución real por clase y split |
| `data/nih/dataset_summary.json` | Metadatos completos |
| `data/nih/labels.json` | Lista de 12 etiquetas usadas |

## Entregables de esta Fase

- [ ] `splits.json` con patient-level splits verificados (0 overlap)
- [ ] `dataset_statistics.csv` con distribución real
- [ ] `dataset_summary.json` con metadatos
- [ ] Configuración de augmentation documentada
- [ ] Cálculo de pos_weight desde TRAIN documentado
- [ ] Confirmación: VALIDATION/TEST sin augmentation
