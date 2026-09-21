# Pacientes, usuarios y sesiones

La pantalla de pacientes permite registrar, consultar, editar y eliminar, con búsqueda del servidor, paginación y errores visibles. Campos: nombres, apellidos, CI, nacimiento, género y teléfono. El CI continúa cifrado. El backend mantiene la prohibición de eliminar pacientes con informes firmados.

Administración de usuarios permite modificar username, email, nombres, apellidos, rol y estado con PATCH. La contraseña vacía conserva la existente. Antes username estaba deshabilitado y los errores al guardar quedaban en la consola. Ahora se muestran en el formulario. El correo no puede asignarse a otro usuario, comparando sin distinguir mayúsculas. La creación de cuentas sigue restringida al administrador; no se añadió registro público ni login con Google.

## Duración de sesión

| Opción | Access JWT | Límite absoluto | Al cerrar la pestaña |
|---|---|---|---|
| Sesión normal | 15 minutos | 8 horas | Los tokens se guardan en sessionStorage |
| Recuérdame | 15 minutos | 30 días | Los tokens persisten en localStorage |

La renovación automática conserva ambos tokens devueltos por el servidor y bloquea el refresh anterior. Las solicitudes concurrentes de una pestaña comparten una sola renovación; Web Locks coordina pestañas cuando el navegador lo soporta. Se renueva cerca del vencimiento, al volver a una pestaña y tras un 401 recuperable. Una caída transitoria de red conserva un refresh válido para reintentar; un token inválido o revocado elimina la sesión. El límite absoluto no se extiende con rotaciones: al alcanzar 8 horas o 30 días se requiere iniciar sesión nuevamente. Nombre y rol se actualizan desde DB al renovar; las API siguen validando los permisos actuales del usuario.

Cerrar sesión elimina los tokens locales inmediatamente y solicita revocar el refresh cuando la conexión y el access lo permiten. Sin conexión no se puede garantizar la revocación del token en el servidor. Cambiar/restablecer la contraseña invalida los tokens anteriores; el reset también elimina la sesión actual del navegador. Mantener Recuérdame desmarcado en equipos compartidos.

## Activar recuperación mediante Gmail

La integración usa SMTP de Gmail para enviar un código de seis dígitos. No usa Google Sign-In ni crea cuentas automáticamente.

1. En la cuenta remitente, habilitar verificación en dos pasos y obtener una contraseña de aplicación si la cuenta lo permite. Google explica sus condiciones en [contraseñas de aplicación](https://support.google.com/accounts/answer/185833).
2. Editar **localmente** `backend/.env`, sustituyendo el EMAIL_BACKEND de memoria y configurando:

```dotenv
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=tu-remitente@gmail.com
EMAIL_HOST_PASSWORD=tu-contraseña-de-aplicación
DEFAULT_FROM_EMAIL=tu-remitente@gmail.com
FRONTEND_URL=http://localhost:5173
```

Los valores de usuario/contraseña anteriores son marcadores: no son credenciales reales. Usar un origen HTTPS real para FRONTEND_URL al desplegar. No cambiar SECRET_KEY ni FERNET_KEY. No publicar .env ni compartir la contraseña en el chat. Reiniciar el backend tras modificar su entorno. Google documenta [SMTP y TLS en puerto 587](https://support.google.com/mail/answer/7104828).

3. El administrador debe asignar a cada usuario su correo de recuperación. Ese correo puede ser Gmail u otro proveedor; el remitente es la cuenta Gmail configurada.
4. En login, elegir **¿Olvidaste tu contraseña?**, introducir el correo registrado, escribir el código de seis dígitos recibido y, tras validarlo, elegir y confirmar la nueva contraseña. El código vence en 10 minutos, admite hasta cinco intentos y deja de servir tras su uso.

El flujo también está disponible en `/recuperar-contrasena`. No se envía ningún enlace ni se ofrecen registro público o Google Sign-In.

**Estado de correo:** el entorno local conserva el backend de memoria de desarrollo. La construcción del correo con código se verificó con outbox de pruebas; no se configuraron credenciales reales ni se certificó entrega SMTP externa. La recepción real necesita completar los pasos anteriores.

## Verificación

Resultados definitivos y archivos afectados en [informe de esta corrección](password-study-review.md). La rotación y blacklist siguen las primitivas del proveedor [Simple JWT](https://django-rest-framework-simplejwt.readthedocs.io/en/latest/settings.html).

No se modificó training, no se inició entrenamiento ni Fase 3 y no hubo commit/push ni alteración del staging previo. Esta corrección incluye la migración `accounts.0005_password_reset_code`; ejecutar `python manage.py migrate` antes de iniciar el backend.
