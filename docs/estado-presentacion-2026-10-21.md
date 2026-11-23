# Estado de presentación — 21 de octubre de 2026

## Objetivo del hito

La entrega correspondiente a la semana del 19 al 25 de octubre cierra la Fase 3:
integración del modelo CNN, presentación coherente de sus cinco categorías,
umbrales centralizados y explicación visual mediante Grad-CAM.

El sistema debe presentarse como apoyo a la revisión radiográfica. Las puntuaciones
del modelo no representan un diagnóstico confirmado ni sustituyen la valoración
del médico radiólogo.

## Alcance listo para demostrar

1. Inicio de sesión y acceso según rol.
2. Registro o selección de paciente.
3. Carga de radiografía de tórax DICOM, PNG, JPG/JPEG, WebP, TIFF o BMP.
4. Validación del archivo, calidad técnica y proyección.
5. Inferencia con `neorx_focused5_v2` a 512 px.
6. Resultados para Enfisema, Edema pulmonar, Derrame pleural, Masa pulmonar y
   Neumotórax, usando el umbral propio de cada categoría.
7. Visualización Grad-CAM para la categoría seleccionada.
8. Generación del preinforme estructurado para revisión profesional, con cada
   sección marcada como pendiente o completa.
9. Visualización autenticada de la radiografía dentro del informe, usando una
   copia PNG normalizada para evitar incompatibilidades del navegador.

## Evidencia verificada el 20 de octubre

| Comprobación | Resultado |
|---|---|
| Checkpoint final | Carga correcta, 5 clases y 5 umbrales |
| Grad-CAM real | Mapa finito de 512 × 512 generado con el checkpoint nuevo |
| Backend | 163 pruebas superadas |
| Frontend | 15 pruebas unitarias activas y 7 pruebas de sesión superadas; se retiraron pruebas de componentes duplicados sin uso |
| Accesibilidad visual | Contraste aprobado en los 7 temas |
| Calidad frontend | ESLint sin errores y compilación Vite de producción correcta |
| Django | Sin migraciones pendientes y `manage.py check` correcto |
| Docker Compose | Configuración válida; producción requiere completar secretos |
| PDF y DICOM SR | Pruebas de exportación superadas |
| Formatos de imagen | DICOM, PNG, JPG/JPEG, WebP, TIFF y BMP validados; copia PNG generada |
| Visor del informe | Acceso privado probado incluso si la API responde con otro alias local del host |

## Guion recomendado de demostración

1. Iniciar backend y frontend antes de la exposición.
2. Ingresar como médico y mostrar el tablero.
3. Abrir un estudio ya procesado para evitar depender únicamente del tiempo de
   inferencia durante la presentación.
4. Explicar las cinco categorías y señalar que cada una posee un umbral obtenido
   en validación.
5. Seleccionar una categoría y mostrar su Grad-CAM.
6. Generar el informe preliminar, completar el checklist clínico y firmarlo.
7. Descargar el PDF. Mostrar DICOM SR como avance adicional si queda tiempo.

## Preparación inmediata antes de presentar

Antes de iniciar los servidores puede ejecutarse el prevuelo automatizado:

```powershell
.\scripts\preflight-presentacion.ps1
```

Para una revisión rápida que omita las suites y la pasada real de Grad-CAM:

```powershell
.\scripts\preflight-presentacion.ps1 -SkipTests -SkipModel
```

```powershell
cd backend
python manage.py check
python manage.py runserver
```

En otra terminal:

```powershell
cd frontend
npm run dev
```

La configuración local usa inferencia `inline`; Redis y Celery no son necesarios
para esta demostración local. El primer análisis tarda más porque carga y
precalienta ResNet-50. Conviene abrir un estudio procesado previamente y conservar
una segunda imagen válida como respaldo.

## Trabajo adelantado respecto al cronograma

- Exportación PDF y DICOM SR implementada y probada.
- Administración de usuarios y actividad implementadas.
- Métricas operativas y tablero funcionales; faltan gráficos y exportación CSV.
- Auditoría, protección de CI, acceso privado a imágenes y rate limiting integrados.
- Swagger/OpenAPI disponible, aunque varios endpoints basados en `APIView` aún
  requieren declarar sus esquemas para que la documentación quede completa.
- Docker de producción, script de despliegue y estrategia de backup disponibles.
- Entrenamiento focused5 concluido e integrado antes de la fecha originalmente
  prevista.

## Riesgos que deben explicarse con honestidad

- Los umbrales de Enfisema y Edema son 0,95 y no detectaron positivos en la
  muestra de validación usada para seleccionarlos; son demasiado conservadores
  para afirmar desempeño clínico suficiente.
- La macro AUC del checkpoint seleccionado es 0,8271, mientras que la macro
  average precision es 0,2468. Deben presentarse ambas métricas y el desbalance
  del conjunto, no solo el mejor porcentaje.
- Falta una evaluación final independiente sobre test antes de afirmar mejora
  frente al modelo baseline.
- Los archivos clínicos tienen acceso autenticado, pero no cifrado binario a nivel
  de aplicación. El despliegue debe proteger el volumen y sus copias de seguridad.

## Siguiente orden de trabajo

1. Ejecutar evaluación final del checkpoint sobre test y generar tablas y curvas.
2. Completar los esquemas OpenAPI de los endpoints `APIView`.
3. Añadir gráficos y exportación CSV al tablero operativo.
4. Medir cobertura y completar las rutas todavía no cubiertas.
5. Preparar datos de demostración, capturas y plan de contingencia sin conexión.
