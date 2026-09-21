# Recuperación por código y área de estudios

## Cambios

| Antes | Ahora | Motivo |
|---|---|---|
| El correo llevaba un enlace de restablecimiento. | Solo una cuenta activa con correo registrado puede solicitar un código numérico de seis dígitos. El código vence a los diez minutos y admite cinco intentos. | Cumplir el flujo solicitado y limitar intentos. |
| El formulario aceptaba solo el nombre de usuario. | Acepta nombre de usuario o correo registrado, sin distinguir mayúsculas en el correo. | Mantener las cuentas creadas por el administrador sin registro público ni Google Sign-In. |
| La creación de estudios aparecía solo para recepción y la vista de análisis guardado no estaba accesible. | Recepción y médicos acceden a «Nuevo estudio». Una radiografía guardada abre `/analisis/:id` con resultados, visor, Grad-CAM y acceso al informe según rol. | Recuperar la lectura y el diagnóstico de estudios existentes. |
| El panel de hallazgos esperaba `niveles_generales`, que la API no devuelve, y podía dejar la página vacía. | Usa `niveles_visuales_generales` y umbrales por patología de la API; ordena hallazgos por probabilidad. | Reparar el contrato real con el backend y la visualización clínica. |

El código se guarda únicamente como HMAC ligado al usuario. Al verificarlo se consume y se entrega una prueba opaca temporal para establecer la nueva contraseña. Cambiarla invalida el acceso y los refresh anteriores. El formulario muestra los pasos correo, código y nueva contraseña en un modal accesible desde login; la ruta directa de recuperación sigue disponible. Un envío fallido elimina el código pendiente y da error explícito.

La pantalla de estudio reutiliza el flujo existente de carga DICOM/imagen, análisis CNN y Grad-CAM. Al reintentar una subida conserva el estudio recién creado para evitar duplicados. La lista y el detalle de estudios exponen la última imagen y enlazan con su análisis. Una imagen pendiente o fallida muestra su estado y permite actualizarlo. El administrador conserva el acceso a gestión y no recibe permiso para subir radiografías.

## Verificación

- Backend: 117 pruebas, cero fallos ni omisiones; `manage.py check` limpio; `makemigrations --check --dry-run` sin cambios.
- Frontend: `npm run lint`, `npm run build` y siete pruebas de sesión aprobadas.
- Navegador aislado: once comprobaciones aprobadas sobre recuperación, login por correo, estudio médico, resultados guardados, rol administrador y modal móvil; sin errores de JavaScript. Datos y resultado CNN de la captura son sintéticos; no constituyen una validación diagnóstica del modelo.
- El staging previo y los archivos de entrenamiento coinciden exactamente con sus snapshots anteriores. No hubo commit ni push.

## Puesta en marcha

Ejecutar `python manage.py migrate` en `backend` para aplicar `accounts.0005_password_reset_code` y reiniciar backend/frontend. Para que los códigos lleguen de verdad, configurar el SMTP de Gmail en `backend/.env` según [gmail-y-sesiones.md](gmail-y-sesiones.md); las pruebas usan un buzón de memoria y no certifican entrega externa.

Evidencia: [pruebas backend](password-study-backend.xml), [comprobaciones de navegador](password-study-review/checks.json), [modal móvil](password-study-review/recuperacion-mobile.png), [análisis guardado](password-study-review/analisis-guardado-medico-desktop.png).
