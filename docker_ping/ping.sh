#!/usr/bin/env sh

if [ -z ${OUTPUT+x} ]; then
  ping "$HOST"
else
  ping "$HOST" | tee "$OUTPUT"
fi
