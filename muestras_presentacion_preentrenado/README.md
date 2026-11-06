# Muestras de presentación verificadas con ResNet-50

Esta carpeta contiene cinco radiografías públicas de NIH ChestX-ray14, una por
cada salida que NeoRX presenta:

1. Derrame pleural (hallazgo específico prioritario).
2. Categoría tumoral.
3. Categoría pleural.
4. Categoría infecciosa.
5. Categoría intersticial.

Cada radiografía tiene dos visualizaciones generadas por el sistema real:
`mapa_calor__*.png` (superposición sobre la placa) y `solo_calor__*.png`.
`reporte_verificacion.json` registra la salida, puntuación técnica, objetivo de
Grad-CAM, hash del archivo y tiempo de ejecución.

## Resultados verificados

| Salida | Imagen | Puntuación técnica |
| --- | --- | ---: |
| Derrame pleural | `01_derrame_pleural__00010834_000.png` | 92,02/100 |
| Tumoral | `02_masa_pulmonar__00009671_004.png` | 99,64/100 |
| Pleural | `04_neumotorax__00027092_004.png` | 97,78/100 |
| Infecciosa | `10_infiltrado__00001381_003.png` | 73,89/100 |
| Intersticial | `08_fibrosis__00004409_001.png` | 50,92/100 |

La verificación se ejecutó dentro del mismo contenedor de NeoRX con
`resnet50-res512-all` y entrada de 512 × 512 px.

## Uso durante la presentación

Suba primero la imagen original desde `http://localhost:8080/escaneo`. Cuando el
análisis termine, pulse **Generar mapa de calor del resultado principal**. El
resultado esperado puede consultarse en `reporte_verificacion.json`.

## Alcance honesto

Las imágenes son una selección curada para demostrar que el flujo técnico
funciona. No constituyen una evaluación independiente ni permiten afirmar un
porcentaje de precisión clínica. El modelo entrega orientación experimental para
revisión profesional; no confirma ni descarta enfermedad.

Fuente: NIH Clinical Center, ChestX-ray14. Los identificadores originales se
conservan en los nombres de archivo.
