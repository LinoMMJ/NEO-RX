-- init-db.sql - Inicialización de base de datos Neo RX
-- Se ejecuta automáticamente al crear el contenedor PostgreSQL

-- Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Configuración de zona horaria
SET timezone = 'America/La_Paz';

-- Comentarios de la base de datos
COMMENT ON DATABASE neorx IS 'Neo RX - Plataforma de Diagnóstico Asistido por IA para Radiografías de Tórax';

-- Índices adicionales para rendimiento (se crean vía migraciones Django, pero aquí como referencia)
-- CREATE INDEX IF NOT EXISTS idx_paciente_ci ON pacientes_paciente (ci);
-- CREATE INDEX IF NOT EXISTS idx_estudio_fecha ON pacientes_estudio (fecha);
-- CREATE INDEX IF NOT EXISTS idx_imagen_estado ON estudios_imagendicom (estado_procesamiento);
-- CREATE INDEX IF NOT EXISTS idx_resultado_fecha ON diagnostico_resultadocnn (fecha_analisis);
-- CREATE INDEX IF NOT EXISTS idx_informe_estado ON informes_informepreliminar (estado);

-- Permisos para usuario de aplicación
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO neorx;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO neorx;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO neorx;

-- Configuración de autovacuum para tablas grandes
ALTER TABLE pacientes_paciente SET (autovacuum_vacuum_scale_factor = 0.05);
ALTER TABLE pacientes_estudio SET (autovacuum_vacuum_scale_factor = 0.05);
ALTER TABLE estudios_imagendicom SET (autovacuum_vacuum_scale_factor = 0.05);
ALTER TABLE diagnostico_resultadocnn SET (autovacuum_vacuum_scale_factor = 0.05);
ALTER TABLE informes_informepreliminar SET (autovacuum_vacuum_scale_factor = 0.05);
ALTER TABLE neorx_auditlog SET (autovacuum_vacuum_scale_factor = 0.01);

-- Configuración de timezone por defecto
ALTER DATABASE neorx SET timezone = 'America/La_Paz';