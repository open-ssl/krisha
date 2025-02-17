-- Подключаемся к базе данных postgres
\c postgres;

-- Создаем пользователя rent_service
CREATE USER rent_service WITH PASSWORD 'rent_service_password';

-- Создаем базу данных rent_service
CREATE DATABASE rent_service;
GRANT ALL PRIVILEGES ON DATABASE rent_service TO rent_service;

-- Подключаемся к базе данных rent_service
\c rent_service;

-- Создаем схему rent_service
CREATE SCHEMA rent_service;

-- Даем права на схему rent_service пользователю rent_service
ALTER SCHEMA rent_service OWNER TO rent_service;
GRANT ALL ON SCHEMA rent_service TO rent_service;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA rent_service TO rent_service;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA rent_service TO rent_service;

-- Устанавливаем права по умолчанию для новых объектов в схеме rent_service
ALTER DEFAULT PRIVILEGES IN SCHEMA rent_service GRANT ALL ON TABLES TO rent_service;
ALTER DEFAULT PRIVILEGES IN SCHEMA rent_service GRANT ALL ON SEQUENCES TO rent_service;

-- Устанавливаем search_path для пользователя rent_service
ALTER USER rent_service SET search_path TO rent_service;

-- Даем права на схему public
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON DATABASE postgres TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;

-- Устанавливаем права по умолчанию для новых объектов
ALTER DEFAULT PRIVILEGES FOR USER postgres IN SCHEMA public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR USER postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres; 