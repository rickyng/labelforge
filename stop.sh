#!/usr/bin/env bash
set -e

pkill -f 'uvicorn backend.main:app' 2>/dev/null && echo 'Backend stopped.' || echo 'Backend not running.'
pkill -f 'vite' 2>/dev/null && echo 'Frontend stopped.' || echo 'Frontend not running.'
