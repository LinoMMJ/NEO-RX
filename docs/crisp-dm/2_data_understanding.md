# CRISP-DM Fase 2: Comprensión de los Datos (Data Understanding)

## Dataset: NIH ChestX-ray14

| Atributo | Valor |
|----------|-------|
| **Fuente** | NIH Clinical Center (Wang et al., 2017) |
| **Acceso** | Box: https://nihcc.app.box.com/v/ChestXray-NIHCC / Kaggle |
| **Tamaño** | ~42 GB imágenes + CSV (~112,120 imágenes frontales) |
| **Formato imágenes** | PNG, 1024x1024 (original), 8-bit grayscale |
| **Metadatos** | `Data_Entry_2017.csv` |
| **Licencia** | Uso académico/investigación |

## Estructura del CSV (`Data_Entry_2017.csv`)

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `Image Index` | string | Nombre de archivo (ej. `00000001_001.png`) |
| `Finding Labels` | string | Etiquetas separadas por `\|` (ej. `Atelectasis\|Consolidation`) |
| `Follow-up #` | int | Número de seguimiento |
| `Patient ID` | int | ID único de paciente (**crítico para splits**) |
| `Patient Age` | string | Edad (ej. `58Y`, `003M`) |
| `Patient Gender` | string | `M` / `F` |
| `View Position` | string | `PA` / `AP` |
| `OriginalImageWidth` | int | Ancho original |
| `OriginalImageHeight` | int | Alto original |
| `OriginalImagePixelSpacing_x` | float | Espaciado píxel X |
| `OriginalImagePixelSpacing_y` | float | Espaciado píxel Y |

## Etiquetas (Finding Labels)

**14 clases NIH originales** (multi-label: una imagen puede tener múltiples etiquetas):

| Etiqueta (EN) | Descripción | Categoría |
|---------------|-------------|-----------|
| Atelectasis | Colapso pulmonar | Pulmonar |
| Cardiomegaly | Cardiomegalia | **Cardiología** |
| Consolidation | Consolidación | Pulmonar |
| Edema | Edema pulmonar | Pulmonar |
| Emphysema | Enfisema | Pulmonar |
| Effusion | Derrame pleural | Pulmonar |
| Fibrosis | Fibrosis pulmonar | Pulmonar |
| Hernia | Hernia | **Otra** |
| Infiltration | Infiltrado pulmonar | Pulmonar |
| Mass | Masa pulmonar | Pulmonar |
| Nodule | Nódulo pulmonar | Pulmonar |
| Pleural_Thickening | Engrosamiento pleural | Pulmonar |
| Pneumonia | Neumonía | Pulmonar |
| Pneumothorax | Neumotórax | Pulmonar |

**Etiqueta especial**: `No Finding` — imagen sin patologías aparentes

## Selección para este Proyecto: 12 Clases Pulmonares

Se **excluyen**: `Cardiomegaly` (cardiología), `Hernia` (no pulmonar)

**Razonamiento**: Objetivo es apoyo a **neumología**. Cardiomegaly es hallazgo cardíaco; Hernia es extremadamente rara (<0.2%) y no neumológica.

## Análisis Exploratorio (PENDIENTE DE EJECUCIÓN EXPERIMENTAL)

Al ejecutar `training.prepare_dataset --source local`, se generarán:

### `dataset_statistics.csv`
```csv
class,total_images,positive_images,negative_images,positive_percentage,train_positive,val_positive,test_positive
Atelectasis,XXXX,XXXX,XXXX,XX.XX,XXXX,XXXX,XXXX
Consolidation,XXXX,XXXX,XXXX,XX.XX,XXXX,XXXX,XXXX
...
```

### `dataset_summary.json`
```json
{
  "total_images": null,
  "total_patients": XXXXX,
  "labels_used": [...],
  "splits": {
    "train": {"images": XXXXX, "patients": XXXXX, ...},
    "val": {"images": XXXXX, "patients": XXXXX, ...},
    "test": {"images": XXXXX, "patients": XXXXX, ...}
  }
}
```

## Validaciones Automáticas Implementadas

1. **Patient-level split verification**: `validate_patient_overlap()` — falla si hay overlap
2. **Column validation**: Verifica columnas requeridas en CSV
3. **Image existence check**: Verifica que archivos existen en `images/`
4. **Duplicate detection**: `Image Index` duplicados en CSV
5. **Label parsing**: Multi-label parsing correcto (`A\|B\|C` → `['A','B','C']`)

## Limitaciones del Dataset (Críticas para Tesis)

| Limitación | Impacto |
|------------|---------|
| **Etiquetas ruidosas** | Extracción automática NLP de informes, no lectura experta → falsos positivos/negativos |
| **Prevalencia sesgada** | Población hospitalaria US ≠ población ambulatoria Bolivia |
| **No hay diagnóstico confirmado** | Etiquetas = hallazgos radiográficos reportados, no verdad clínica |
| **Solo frontales** | No incluye laterales (LAT) en dataset principal |
| **Desbalance severo** | Hernia ~0.2%, Nodule ~5%, Infiltration ~18% |
| **Sin datos locales** | No representa distribución de Neo Rayos X Digital |

## Entregables de esta Fase

- [ ] `dataset_statistics.csv` generado (tras descarga)
- [ ] `dataset_summary.json` generado
- [ ] Verificación patient-level splits (0 overlap)
- [ ] Análisis de desbalance por clase documentado
- [ ] Limitaciones declaradas en tesis
Los bloques de salida son ejemplos de formato. No acreditan un dataset local adquirido ni estadísticas calculadas. Resultado pendiente de ejecución experimental.
