# CRISP-DM Fase 1: Comprensión del Negocio (Business Understanding)

## Objetivo del Proyecto

Desarrollar un **sistema web de apoyo a la interpretación radiológica** basado en redes neuronales convolucionales (ResNet-50 + Transfer Learning) para la reducción de tiempos en informes de tórax de enfermedades neumológicas en el centro **Neo Rayos X Digital**, La Paz, Bolivia.

## Alcance

- **Modalidad**: Radiografías digitales de tórax (proyecciones PA, AP, LAT)
- **Patologías objetivo**: Hallazgos neumológicos (no cardiológicos)
- **Usuario final**: Médicos radiólogos / médicos generales que interpretan RX de tórax
- **Rol del sistema**: **Apoyo a la interpretación** — NO reemplaza al médico
- **Salida**: Hallazgos detectados con probabilidad estimada, para revisión profesional

## Problema de Negocio

1. **Tiempo de elaboración de informes**: Los radiólogos dedican tiempo significativo a revisar radiografías normales y buscar hallazgos sutiles
2. **Variabilidad inter-observador**: Diferentes radiólogos pueden detectar/omitir hallazgos
3. **Carga de trabajo**: Aumento de estudios de tórax post-COVID
4. **Necesidad**: Herramienta que priorice hallazgos probables y reduzca tiempo de lectura

## Restricciones y Requisitos

| Restricción | Detalle |
|-------------|---------|
| **Regulatoria** | Sistema de apoyo (no diagnóstico), requiere validación médica |
| **Datos** | No hay dataset propio suficiente de Neo Rayos X → usar NIH ChestX-ray14 público |
| **Técnica** | ResNet-50 preentrenado (torchxrayvision), Transfer Learning |
| **Metodología** | CRISP-DM para trazabilidad académica |
| **Ética** | No datos de pacientes reales sin consentimiento; anonimización obligatoria |
| **Despliegue** | Integración con Django + Celery existente |

## Stakeholders

- **Centro Neo Rayos X Digital**: Propietario, validador clínico
- **Médicos radiólogos**: Usuarios finales, validadores de salida
- **Equipo de desarrollo**: Implementación técnica
- **Tribunal de grado**: Evaluación académica

## Criterios de Éxito (Académicos/Metodológicos)

1. **Reproducibilidad**: Pipeline completo documentado, seeds fijas, splits patient-level
2. **Rigor metodológico**: Sin data leakage (thresholds en VALIDATION, no TEST)
3. **Métricas reales**: AUC, Sensibilidad, Especificidad, F1 por clase + macro/micro
4. **Documentación CRISP-DM**: Trazabilidad completa 6 fases
5. **Integración funcional**: Checkpoint cargado en Django, inferencia end-to-end

## Limitaciones Conocidas (Previas a Ejecución)

- NIH ChestX-ray14 tiene etiquetas ruidosas (extracción automática de informes, no lectura experta)
- Prevalencia en NIH ≠ prevalencia en población de Neo Rayos X (Bolivia)
- Etiquetas NIH = hallazgos radiográficos, **NO diagnósticos clínicos confirmados**
- Modelo fine-tuned en NIH ≠ rendimiento garantizado en datos locales
- **PENDIENTE DE EJECUCIÓN EXPERIMENTAL**: Todas las métricas cuantitativas

## Entregables de esta Fase

- [x] Definición del problema y alcance
- [x] Identificación de stakeholders
- [x] Criterios de éxito metodológicos
- [x] Limitaciones declaradas
- [ ] Plan de proyecto con hitos (ver cronograma separado)
