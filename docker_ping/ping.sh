#!/usr/bin/env bash

hostname > "$OUTPUT"
set -o pipefail
if [ -z ${OUTPUT+x} ]; then
  ping "$HOST"
else
  ping "$HOST" 2>&1 | tee -a "$OUTPUT"
fi
