#!/usr/bin/env bash
set -e

docker compose up --build -d
echo "LabelForge running at http://localhost:8000"
