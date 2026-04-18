-- Bootstrap script for Postgres first-run only.
-- Creates a dedicated keycloak database + user, isolated from the app DB.
-- Variables substituted by Postgres image via env vars at init time are NOT available here,
-- so we hard-code the database name and use a role that is created by the bootstrap
-- followed by a role-alteration using the password provided via env var inside the container.
-- The keycloak role is created here with a placeholder password and the real password
-- is set at first keycloak boot via the KC_DB_PASSWORD env var and an ALTER ROLE statement
-- executed by the bootstrap-db.sh script.

\set keycloak_db 'keycloak'

CREATE DATABASE keycloak;
CREATE ROLE keycloak WITH LOGIN PASSWORD 'CHANGE_ME_KEYCLOAK_BOOTSTRAP';
GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak;

\c keycloak
GRANT ALL ON SCHEMA public TO keycloak;
