#!/usr/bin/env sh

if [ -z ${OUTPUT+x} ]; then
  ping "$HOST"
else
  ping "$HOST" 2>&1 | tee "$OUTPUT"
fi
