#!/bin/sh
# Life Dashboard — update + herbouw op de NAS.
# Geen git nodig op de NAS: de pull draait in een wegwerp git-container.
# Draai met sudo (Docker vereist root op DSM):
#     sudo sh /volume1/docker/life-dashboard/deploy.sh
set -e
cd "$(dirname "$0")"

echo "[deploy] nieuwste code ophalen (git-container)..."
docker run --rm -v "$PWD":/repo -w /repo alpine/git pull

echo "[deploy] image bouwen en container (her)starten..."
docker compose up -d --build

echo "[deploy] klaar. Open http://<nas-ip>:${HOST_PORT:-8765}"
