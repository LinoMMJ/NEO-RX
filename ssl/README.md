# Certificados TLS

El proxy de producción espera dos archivos que no se versionan:

- `fullchain.pem`
- `privkey.pem`

Copia aquí certificados emitidos para el dominio antes de ejecutar `docker compose -f docker-compose.prod.yml up`. No subas claves privadas al repositorio. En despliegues con TLS terminado por un balanceador o proveedor, adapta el proxy para recibir HTTP únicamente desde ese balanceador.
