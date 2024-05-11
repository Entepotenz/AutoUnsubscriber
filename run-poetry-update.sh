#!/usr/bin/env bash

set -o errexit
set -o pipefail
set -o nounset
if [[ "${TRACE-0}" == "1" ]]; then set -o xtrace; fi

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

IMAGE_NAME=$(grep -m 1 "^FROM" "$SCRIPT_DIR/Dockerfile" | awk '{print $2}')

docker run --rm \
    --pull always \
    -it \
    -v "$SCRIPT_DIR/:/source" \
    -v "/source/.venv" \
    "$IMAGE_NAME" sh -c "\
    apk update && apk add build-base libffi-dev; \
    pip install poetry; \
    cd /source; \
    poetry self add poetry-plugin-export; \
    poetry update; \
    poetry lock; \
    poetry export --format requirements.txt --without dev --output /source/requirements.txt; \
    poetry export --format requirements.txt --with dev --output /source/requirements-dev.txt;"
