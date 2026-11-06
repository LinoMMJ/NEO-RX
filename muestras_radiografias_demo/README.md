# Muestras públicas para demostración de NeoRX

Carpeta creada el 3 de noviembre de 2026 con radiografías públicas y desidentificadas de NIH ChestX-ray14. Cada archivo conserva en el nombre el identificador original del conjunto.

## Resultado comprobado en el sistema desplegado

| Archivo | Etiqueta NIH | Salida obtenida en NeoRX | Puntuación técnica |
| --- | --- | --- | ---: |
| `01_derrame_pleural__00010834_000.png` | Effusion | Derrame pleural | 99,75 % |
| `02_masa_pulmonar__00009671_004.png` | Mass | Tumoral | 99,99 % |
| `03_nodulo_pulmonar__00028416_001.png` | Nodule | Tumoral | 99,99 % |
| `04_neumotorax__00027092_004.png` | Pneumothorax | Pleural | 96,49 % |
| `05_engrosamiento_pleural__00019373_012.png` | Pleural Thickening | Pleural | 89,90 % |
| `06_neumonia__00026629_006.png` | Pneumonia | Infecciosa | 81,16 % |
| `07_consolidacion__00005600_011.png` | Consolidation | Infecciosa | 50,50 % |
| `08_fibrosis__00004409_001.png` | Fibrosis | Intersticial | 85,19 % |
| `09_edema__00003534_037.png` | Edema | Intersticial | 91,54 % |
| `10_infiltrado__00001381_003.png` | Infiltration | Intersticial | 94,01 % |

Las diez imágenes fueron ejecutadas nuevamente contra el contenedor `celery_worker` y el checkpoint activo `neorx_effusion_categories_v1`. Resultado de esta selección: 10/10 rutas esperadas.

## Cómo utilizarlas

1. Abrir `http://localhost:8080/escaneo`.
2. Seleccionar una imagen de esta carpeta.
3. Asociarla a un paciente de demostración y ejecutar el análisis.
4. Esperar aproximadamente 10–15 segundos.
5. Comparar el resultado con la tabla anterior.

## Alcance y procedencia

- Fuente original: NIH Clinical Center, ChestX-ray14.
- Copia pública utilizada: `https://nih-chest-x-rays.s3.us-east-2.amazonaws.com/images_1024x1024/`.
- `seleccion.json` conserva identificador, etiqueta de origen, puntuaciones congeladas y URL exacta.
- Las etiquetas NIH fueron extraídas automáticamente de informes y pueden contener ruido.
- Esta es una selección curada a partir de VALIDACIÓN para una demostración funcional. No debe presentarse como una prueba independiente, tasa de exactitud, validación clínica ni evidencia de que el sistema acertará 10 de cada 10 radiografías nuevas.
- Las puntuaciones mostradas son activaciones técnicas del modelo, no porcentajes de certeza diagnóstica.

La carpeta `descartadas_primera_prueba` conserva la primera selección que reveló resultados ambiguos o incorrectos. Se mantiene como evidencia de que la comprobación no fue ocultada.
