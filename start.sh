#!/usr/bin/env bash
# Default startup — includes postgres. Skip --profile with-postgres if you have your own DB.
docker compose --profile with-postgres "$@"