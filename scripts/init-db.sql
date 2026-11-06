-- init-db.sql - Inicialización de base de datos Neo RX
-- Se ejecuta automáticamente al crear el contenedor PostgreSQL

-- Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Configuración de zona horaria
SET timezone = 'America/La_Paz';

-- PostgreSQL crea POSTGRES_DB con POSTGRES_USER como propietario. Los permisos,
-- tablas e índices restantes los gestionan exclusivamente las migraciones de
-- Django. Este script se ejecuta antes de las migraciones y por eso no debe
-- referenciar tablas de la aplicación ni nombres de usuario fijos.
