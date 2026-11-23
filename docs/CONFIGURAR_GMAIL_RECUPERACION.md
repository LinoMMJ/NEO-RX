# Configurar recuperación de contraseña con Gmail

Neo RX envía un código numérico de seis dígitos, válido durante 15 minutos y de un solo uso. Las credenciales de Gmail deben configurarse únicamente en el archivo `.env`; nunca deben subirse al repositorio.

## 1. Preparar la cuenta de Google

1. Activa la verificación en dos pasos de la cuenta que enviará los correos.
2. Abre [Contraseñas de aplicaciones de Google](https://myaccount.google.com/apppasswords).
3. Crea una contraseña para `Neo RX` y copia el código de 16 caracteres.

Google documenta que las contraseñas de aplicación requieren verificación en dos pasos: [Ayuda oficial de Google](https://support.google.com/mail/answer/185833?hl=es).

## 2. Configurar `.env`

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=tu_cuenta@gmail.com
EMAIL_HOST_PASSWORD=contraseña_de_aplicacion_de_16_caracteres
DEFAULT_FROM_EMAIL=tu_cuenta@gmail.com
PASSWORD_RESET_CODE_MINUTES=15
```

No uses la contraseña normal de Gmail. `DEFAULT_FROM_EMAIL` debe ser la misma cuenta autorizada para enviar.

## 3. Reiniciar y probar

Reinicia el backend o los contenedores después de modificar `.env`. Verifica además que el usuario tenga un correo único registrado desde Administración → Usuarios.

En el login selecciona **¿Olvidaste tu contraseña?**, introduce el correo, verifica el código recibido y establece la contraseña nueva. Al completarse, el modal se cierra y el sistema vuelve al login.
