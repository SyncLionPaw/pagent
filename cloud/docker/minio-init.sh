#!/bin/sh
set -eu

echo "waiting for minio..."
until mc alias set local "$MINIO_ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1; do
  sleep 1
done

mc mb --ignore-existing "local/${S3_BUCKET}"
mc anonymous set none "local/${S3_BUCKET}"
echo "bucket ready: ${S3_BUCKET}"
