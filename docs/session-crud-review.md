# Corrección de CRUD y sesiones

## Cambios

- Pacientes: alta, consulta, edición y eliminación desde la pantalla, datos completos, búsqueda del servidor, paginación y validación visible. Se conserva el CI cifrado y el bloqueo de eliminación si hay informes firmados.
- Usuarios: username ya no está deshabilitado al editar; PATCH actualiza los datos y el estado. Contraseña vacía conserva la anterior. Los errores se muestran en el formulario y hay notificación de éxito. El correo de recuperación no puede repetirse entre cuentas, sin distinguir mayúsculas. Superusuarios mantienen su gestión por Django admin, como antes.
- Login: Recuérdame y enlace de recuperación, sin registro ni autenticación social. Sólo el administrador crea las cuentas.
- JWT: access 15 minutos; sesión normal 8 horas; recordada 30 días. Se guardan ambos tokens rotados, se conserva la blacklist y se aplica un vencimiento absoluto. Refresh actualiza identidad/rol desde DB y rechaza cuentas inactivas o contraseña modificada.
- Frontend: almacenamiento por pestaña o persistente según opción; renovación preventiva y tras 401; una renovación compartida entre peticiones y coordinación entre pestañas mediante Web Locks cuando existe. Una respuesta tardía no reabre una sesión cerrada. Una caída de red no elimina automáticamente un refresh válido.
- Recuperación: correo configurable mediante SMTP Gmail y enlace a una pantalla para elegir/confirmar contraseña. Token de una hora, hash en DB y uso único; permanece la invalidación de tokens anteriores. El enlace usa fragmento en lugar de query para el token.

## Verificación definitiva

| Comprobación | Resultado |
|---|---|
| Backend completo | 106 PASS; 0 FAIL/ERROR/SKIP |
| Pruebas anteriores de Fase 2.2 | 97 conservadas y aprobadas |
| Nuevas pruebas backend | 9 PASS |
| Pruebas frontend Axios/sesión | 7 PASS; 0 FAIL/SKIP |
| Build frontend | PASS; advertencia existente por tamaño de bundle |
| Django check | 0 problemas |
| Makemigrations check/dry-run | No changes detected |
| Training | Inventario y hashes de 12 archivos idénticos |
| Staging previo | Diff byte a byte idéntico |

[Pytest](session-crud-tests.txt), [JUnit](session-crud-tests.xml), [pruebas frontend](session-crud-frontend-tests.txt), [build](session-crud-frontend-build.txt), [Django](session-crud-django.txt), [migraciones](session-crud-migrations.txt), [resumen](session-crud-verification.json).

No se hicieron migraciones nuevas, cambios a pacientes reales, commits, push ni entrenamiento. Se preservó el trabajo anterior y no se inició Fase 3. No se afirma QA manual de estas pantallas ni entrega SMTP externa: se verificaron los contratos backend, sesiones con el Axios real y compilación.

## Gmail: único paso externo pendiente

El entorno local conserva correo de memoria. Para recibir mensajes reales hay que configurar una cuenta remitente y su contraseña de aplicación en el .env ignorado, seleccionar el backend SMTP y reiniciar backend. No se añadió ninguna credencial real ni se enviaron mensajes externos.

[Pasos exactos y comportamiento de sesiones](gmail-y-sesiones.md). Google documenta [contraseñas de aplicación](https://support.google.com/accounts/answer/185833) y [SMTP TLS 587](https://support.google.com/mail/answer/7104828). La rotación se apoya en [Simple JWT](https://django-rest-framework-simplejwt.readthedocs.io/en/latest/settings.html).

## Archivos

Backend: accounts/serializers.py, accounts/views.py, accounts/test_session_crud.py, neorx/settings.py y .env.example.

Frontend: App.jsx, api/{auth,axios,pacientes,session,errors}.js, context/AuthContext.jsx, pages/{LoginPage,PacientesPage,AdminUsuariosPage,PasswordResetPage}.jsx, tests/session.test.js y package.json (script npm test; sin dependencias nuevas).

La skill ui-ux-pro-max aportó criterios de formularios, errores visibles, controles etiquetados, foco y teclado. Su script auxiliar de búsqueda no está presente en la ruta referenciada del repositorio; se aplicaron las instrucciones disponibles y los estilos existentes.
