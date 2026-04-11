#!/usr/bin/env bash

# ─── Configuration ────────────────────────────────────────────────
POSTGRES_IMAGE="postgres:16"
CONTAINER_NAME="my-postgres"
POSTGRES_USER="myuser"
POSTGRES_PASSWORD="mypassword"
POSTGRES_DB="nifty50"
HOST_PORT=5433
DATA_DIR="$HOME/postgres-data"
# ──────────────────────────────────────────────────────────────────

echo "==> Checking if Docker is running..."
if ! docker info > /dev/null 2>&1; then
  echo "ERROR: Docker is not running. Please start Docker Desktop and try again."
  exit 1
fi

# Pull image only if it doesn't exist locally
echo "==> Checking if image '${POSTGRES_IMAGE}' exists locally..."
if ! docker image inspect "${POSTGRES_IMAGE}" > /dev/null 2>&1; then
  echo "==> Image not found. Pulling '${POSTGRES_IMAGE}' from Docker Hub..."
  docker pull "${POSTGRES_IMAGE}"
  if [ $? -ne 0 ]; then
    echo "ERROR: Failed to pull image '${POSTGRES_IMAGE}'."
    exit 1
  fi
  echo "==> Image pulled successfully."
else
  echo "==> Image '${POSTGRES_IMAGE}' already exists. Skipping pull."
fi

# ─── Ensure user/db exist (idempotent) ────────────────────────────
ensure_user_and_db() {
  echo "==> Waiting for PostgreSQL to be ready..."
  local max_retries=20
  local i=0
  until docker exec "${CONTAINER_NAME}" pg_isready -h localhost -U postgres > /dev/null 2>&1; do
    i=$((i + 1))
    if [ $i -ge $max_retries ]; then
      echo "ERROR: PostgreSQL did not become ready after ${max_retries} attempts. Aborting."
      docker logs "${CONTAINER_NAME}"
      exit 1
    fi
    echo "    ... waiting (${i}/${max_retries})"
    sleep 2
  done
  echo "==> PostgreSQL is ready."

  echo "==> Ensuring role '${POSTGRES_USER}' exists..."
  docker exec -i "${CONTAINER_NAME}" psql -h localhost -U postgres <<-EOSQL
    DO \$\$
    BEGIN
      IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${POSTGRES_USER}') THEN
        CREATE USER ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';
        RAISE NOTICE 'User ${POSTGRES_USER} created.';
      ELSE
        ALTER USER ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';
        RAISE NOTICE 'User ${POSTGRES_USER} already exists. Password updated.';
      END IF;
    END
    \$\$;

    SELECT 'CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER}'
    WHERE NOT EXISTS (
      SELECT FROM pg_database WHERE datname = '${POSTGRES_DB}'
    )\gexec

    GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB} TO ${POSTGRES_USER};
EOSQL

  if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create user/database."
    exit 1
  fi
  echo "==> User and database are ready."
}

# ─── Container lifecycle ──────────────────────────────────────────
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "==> Container '${CONTAINER_NAME}' is already running."
  else
    echo "==> Container '${CONTAINER_NAME}' exists but is stopped. Starting it..."
    docker start "${CONTAINER_NAME}"
  fi
else
  mkdir -p "${DATA_DIR}"
  echo "==> Creating and starting container '${CONTAINER_NAME}'..."
  docker run --name "${CONTAINER_NAME}" \
    -e POSTGRES_USER=postgres \
    -e POSTGRES_PASSWORD=postgres \
    -p "${HOST_PORT}":5432 \
    -v "${DATA_DIR}":/var/lib/postgresql/data \
    --restart unless-stopped \
    -d "${POSTGRES_IMAGE}"

  if [ $? -ne 0 ]; then
    echo "ERROR: Failed to start container."
    exit 1
  fi
fi

# Always ensure user/db exist (safe to run on every startup)
ensure_user_and_db

echo ""
echo "✅ PostgreSQL is running!"
echo "   Host:     localhost"
echo "   Port:     ${HOST_PORT}"
echo "   User:     ${POSTGRES_USER}"
echo "   Password: ${POSTGRES_PASSWORD}"
echo "   Database: ${POSTGRES_DB}"
echo ""
echo "   Connect:  docker exec -it ${CONTAINER_NAME} psql -U ${POSTGRES_USER} -d ${POSTGRES_DB}"