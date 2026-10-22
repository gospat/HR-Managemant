#!/bin/sh
set -eu
# Migrations are a separate release task, never a worker-startup race.
exec "$@"
