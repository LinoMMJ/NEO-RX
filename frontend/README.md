# Frontend de Neo RX

Interfaz React 19 para la gestión de pacientes, estudios radiológicos, resultados de la CNN, informes, métricas y administración de usuarios.

## Comandos

```powershell
npm install
npm run dev
npm run lint
npm test
npm run build
npm run preview
```

`npm test` ejecuta las pruebas unitarias, las pruebas de sesión JWT y la validación de contraste de todos los temas.

## API

La URL predeterminada es `http://localhost:8000/api`. Para cambiarla crea `.env.local`:

```text
VITE_API_URL=https://tu-dominio.com/api
```

## Criterios de interfaz

- Los permisos y opciones visibles dependen del rol autenticado.
- Los resultados de la CNN siempre se presentan como apoyo para revisión médica.
- Los temas conservan contraste comprobado y respetan `prefers-reduced-motion`.
- Los archivos clínicos se consultan mediante endpoints autenticados; no se enlazan como medios públicos.
