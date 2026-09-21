# Propuesta de mejora del frontend Neo RX

Estado: auditoría y propuesta; las pantallas y funcionalidades nuevas todavía no se implementaron. Se conserva el trabajo existente. Prioridad confirmada: médico y recepción centrados en pacientes; administrador con operación de pacientes y control administrativo. Propuesta para admin: un solo tablero con pestañas Operación y Administración, manteniendo el rango de fechas al cambiar de vista.

## Dirección

Lo leo como una aplicación clínica de trabajo diario para recepción, médicos y administración, con lenguaje sobrio, legible y preciso. Mantener la identidad azul marino/celeste, ordenar la jerarquía y reservar los colores de estado para información real. Tipografía funcional, tablas compactas legibles, formularios agrupados y acciones consistentes. Animaciones breves de estado y respeto por movimiento reducido.

Impeccable guía el modo Operate de tablas/formularios. Emil guía foco, teclado y respuesta de controles. Taste se aplica a landing/login y preservación de identidad; su propio alcance excluye dashboards y tablas, por lo que no impondrá patrones de marketing a las pantallas clínicas.

## Hallazgos comprobados en código

`npm run lint` termina con código 1: **31 errores y 1 warning**. Parte corresponde a imports, reglas de efectos/React Refresh y entorno Node de tests; no se presentan todos como fallos de ejecución. [Salida](frontend-audit-lint.txt).

| Prioridad | Antes (Before) | Propuesta (After) | Motivo/evidencia |
|---|---|---|---|
| P1 | BarraFidelidad retorna antes de useState/useEffect cuando no hay probabilidad | Hooks siempre en el mismo orden; retorno después | ESLint verifica hooks condicionales: cambiar de sin resultado a resultado puede romper el componente |
| P1 | Formularios usan input, label, btn-primary y btn-secondary sin definiciones CSS compartidas | Controles compartidos con borde, altura, foco, error, deshabilitado y carga | No se encuentran estas definiciones en CSS; afecta pacientes, usuarios y recuperación |
| P1 | Sidebar se expande por hover; Layout conserva margen de 72px | Navegación con control por teclado y drawer móvil, sin cubrir el contenido | Sidebar.jsx y Layout.jsx; las etiquetas dependen del ratón |
| P1 | Tablero respalda cifras con una lista paginada y usa || para ceros | Métricas agregadas del backend, cero válido y error/carga diferenciados | DashboardPage.jsx; un total parcial no debe parecer el total real |
| P2 | ToastContext recrea toast; Dashboard depende de [toast] | Notificaciones estables y solicitudes cancelables | Mostrar un toast cambia la referencia y puede provocar una nueva carga de estudios |
| P2 | text-${iconColor} y clase literal {color} | Mapa explícito de clases de estado | DashboardPage.jsx; estilos no fiables con generación estática Tailwind |
| P2 | Estudios redirige a Escaneo | Lista real de estudios con filtros y detalle | App.jsx; el enlace actual no ofrece la lista que anuncia |
| P2 | Textos anuncian entrenamiento con más de 112.000 imágenes | Describir sólo capacidades y estado realmente acreditados | LandingPage/LoginPage/PanelResultados; se mantiene pendiente la autorización de entrenamiento y evaluación |

Es una revisión de código y lint. No se certifica contraste WCAG ni comportamiento en dispositivos reales sin la siguiente pasada visual y funcional.

## Paquete base recomendado

1. Corregir los issues anteriores sin desactivar reglas globalmente para ocultarlos; configurar por separado globals de los tests.
2. Unificar campos, botones, tablas, estados vacíos, carga y notificaciones.
3. Mejorar formularios: identificación, datos personales y contacto; errores junto al campo; foco al primer error; cancelación; prevención de doble envío; confirmación clara para eliminar.
4. Ajustar navegación móvil, breadcrumbs correctos y controles accesibles con teclado.
5. Mantener CRUD, JWT, recuperación y acceso privado a imágenes ya implementados, junto con sus pruebas.

## Pacientes y filtros

| Filtro/acción | Comportamiento | Trabajo necesario |
|---|---|---|
| Nombre o CI | Búsqueda del servidor sobre toda la lista paginada | Ya existe; conservar cifrado y búsquedas actuales |
| Género | Selector con opción todos | Backend ya lo permite |
| Fecha de registro desde/hasta | Rango validado con limpiar filtros | Backend ya recibe fecha_desde/fecha_hasta; aclarar que es registro, no nacimiento |
| Ordenamiento | Nombre, apellidos, CI, fecha de registro o nacimiento | Backend ya lo permite; CI conserva orden lógico |
| Tamaño de página | 10, 20, 50; total y paginación | Backend permite page_size |
| Filtros activos | Chips, cantidad y Limpiar; estado en URL | Frontend |
| Edad o rango de nacimiento | Rango real, independiente de fecha de registro | Extensión explícita del backend si se aprueba |

Añadir una ficha de paciente con pestañas **Datos / Estudios / Informes**. No confundir historial clínico del paciente con auditoría de movimientos del sistema.

## Secciones propuestas

| Sección | Utilidad | Alcance y permisos |
|---|---|---|
| Tablero | Resumen del día, pendientes, errores de procesamiento y accesos rápidos | Mejorar el dashboard existente; no duplicarlo. Médico/recepción: pacientes y pendientes. Admin: pestañas Operación y Administración |
| Estudios | Lista de estudios por paciente, fecha y estado, con acceso al detalle | Nueva pantalla sobre APIs existentes; ajustar filtros según capacidades reales |
| Pendientes | Cola operativa: por procesar, requiere repetición, informes sin firmar y fallos | Acciones según rol; priorización por antigüedad, sin inventar urgencia clínica basada en IA |
| Historial de movimientos | Quién hizo qué, cuándo y sobre qué registro | AuditLog ya existe, pero requiere endpoint de sólo lectura, filtros y permisos. Admin: vista global; otros roles: alcance autorizado definido antes de implementar |
| Ficha del paciente | Datos, estudios e informes en un lugar | Aprovechar relaciones existentes y conservar las restricciones de acceso |
| Perfil y sesión | Datos de cuenta, cambio de contraseña propio y cerrar sesiones | Requiere endpoints de cuenta propia; no permitir asignarse roles ni crear cuentas |

Para movimientos, mostrar fecha/hora, usuario, acción, tipo e ID del registro y resultado cuando exista. No mostrar contraseñas, JWT, claves, tokens de recuperación ni snapshots completos con datos sensibles. No afirmar auditoría exhaustiva de acciones que todavía no registran eventos.

Primera entrega sugerida: **paquete base + filtros de pacientes + tablero + estudios + pendientes + historial**. Ficha y perfil pueden ser una segunda entrega o incorporarse si prefieres aprobar el conjunto.

No propongo agenda, facturación o triaje automático en esta entrega: requieren confirmar procesos y datos que no están definidos en el proyecto.

## Cómo se verificará al implementar

Lint, build, pruebas existentes y nuevas de filtros/roles/estados, una pasada conjunta desktop+móvil y una confirmación tras corregir hallazgos. Sin datos clínicos ficticios presentados como reales, sin cifras experimentales inventadas, sin modificar training, sin alterar staging ni iniciar Fase 3.

La implementación de las nuevas secciones queda sujeta a tu selección, tal como pediste. La ausencia de PRODUCT.md/DESIGN.md no impidió auditar el código existente; el contexto de producto y diseño se fijará con la dirección elegida antes del rediseño.
