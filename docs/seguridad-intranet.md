# Seguridad para el despliegue intranet de Neo RX

## Controles integrados

| Control solicitado | Estado en Neo RX |
|---|---|
| Ocultar API keys y secretos | Integrado. `.env` está ignorado y producción falla si faltan `SECRET_KEY` o `FERNET_KEY`. |
| Secretos en historial Git | Escaneable con `python scripts/scan_secrets_history.py`; nunca imprime el valor encontrado. |
| “Clave pública” de base de datos | No aplica. PostgreSQL requiere una credencial privada de servicio; el puerto no se publica fuera de la red Docker. |
| Row-level security | Sustituido conscientemente por RBAC del servidor. La clínica comparte expediente entre roles autorizados y Django usa una conexión de servicio común. |
| Cifrado de datos sensibles | CI cifrado con Fernet e índice HMAC. DICOM y respaldos requieren cifrado del volumen del servidor, por ejemplo BitLocker. |
| Autenticación del servidor | Integrada con JWT firmado, expiración, rotación, lista de revocación y comprobación de usuario activo. |
| Acceso a registros | Integrado mediante permisos por rol, medios privados y actividad limitada al propio usuario salvo administradores. |
| Manipulación de campos | Endurecida con campos explícitos y de solo lectura para resultados CNN, imágenes y campos de firma. |
| Cookies | `HttpOnly`, `Secure` en producción y `SameSite=Strict` para Django Admin y CSRF. |
| Contraseñas | Django las almacena con hash y salt; nunca se serializan. También aplica validadores de fortaleza. |
| Rate limiting de login | 5 solicitudes/minuto por IP y 10 intentos/hora por identificador anonimizado; Nginx agrega otro límite. |
| Protección contra bots | Doble límite por IP/cuenta, sin registro público y servicio accesible únicamente en intranet. No se añade CAPTCHA externo. |
| Queries parametrizadas | ORM de Django y parámetros del driver. No se concatenan valores del usuario en SQL. |
| Validación de inputs | Serializers, choices, límites, fechas, estados y validación de texto normalizado. |
| Sanitización | Se rechazan controles invisibles y se limita longitud; React y las plantillas Django escapan la salida. |
| Archivos | Una imagen por request, límite de tamaño, extensión, firma binaria, integridad y dimensiones. La vista previa DICOM usa la misma validación. |
| Respuestas mínimas | Serializers con listas explícitas; contraseñas, hashes e índices internos no salen en la API. |
| Security headers | CSP, HSTS, anti-frame, nosniff, política de referencia, permisos y aislamiento de recursos. |
| HTTPS | Nginx redirige HTTP a HTTPS; Django confía solo en el encabezado del proxy y fuerza HTTPS fuera de debug. |
| Dependencias | `npm audit --omit=dev`, `pip-audit -r backend/requirements.txt` y Docker Scout antes de cada tag. |

## Red local recomendada

El servidor debe tener una IP fija de la LAN y aceptar conexiones 443 únicamente desde las subredes de la clínica. PostgreSQL, Redis, Django y Celery permanecen en la red privada de Docker; solo Nginx publica 80/443. El certificado TLS puede provenir de la autoridad interna de la organización y debe instalarse como confiable en los equipos cliente.

El firewall del host debe denegar acceso entrante a 5432, 6379 y 8000. Docker Compose no publica esos puertos, pero la regla del host protege también contra cambios accidentales futuros.

## Cifrado local

El CI se cifra dentro de la aplicación. Los DICOM deben permanecer legibles para pydicom y la CNN, por lo que el control adecuado es cifrar el volumen completo del servidor y el destino de los respaldos. En Windows se recomienda BitLocker; en Linux, LUKS. La clave de recuperación se conserva fuera del servidor.

## Verificación antes de un tag

```powershell
python scripts/scan_secrets_history.py
cd frontend
npm audit --omit=dev
cd ..\backend
pip-audit -r requirements.txt
cd ..
docker scout cves local://neorx-backend:latest
python backend/manage.py check --deploy
```

Si el escáner de historial detecta un secreto real, primero se revoca o rota. Después se limpia todo el historial con `git filter-repo` y se coordina el `force-push`; borrar únicamente el archivo del último commit no elimina el secreto de Git.
