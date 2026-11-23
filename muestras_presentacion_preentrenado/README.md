# Cinco muestras nuevas verificadas en NeoRX

Estas imágenes fueron seleccionadas de NIH ChestX-ray14 y pasadas por el
mismo ResNet-50 y Grad-CAM regional que utiliza el sistema.

| Salida demostrativa | Archivo | Puntuación técnica |
| --- | --- | ---: |
| Derrame pleural | `01_derrame_pleural__00008777_001.png` | 90.72/100 |
| Categoría tumoral | `02_categoria_tumoral__00006832_014.png` | 99.72/100 |
| Categoría pleural | `03_categoria_pleural__00008334_000.png` | 60.15/100 |
| Categoría infecciosa | `04_categoria_infecciosa__00011366_002.png` | 54.76/100 |
| Categoría intersticial | `05_categoria_intersticial__00004747_000.png` | 64.56/100 |

Cada original tiene `mapa_calor__*.png` y `solo_calor__*.png`.
Las cinco cargas también fueron verificadas por la API Docker completa el
10 de noviembre de 2026; consulta `reporte_api_docker.json`.
El control técnico usó `NEORX_BLUR_THRESHOLD=50` y la decisión CNN conservó
su umbral de 0,50.
La puntuación es una activación técnica, no certeza diagnóstica.
La selección es curada para demostración y no constituye una evaluación independiente.

Fuente oficial: https://nihcc.app.box.com/v/ChestXray-NIHCC
