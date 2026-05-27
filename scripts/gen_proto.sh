#!/usr/bin/env bash
set -euo pipefail
# Generate Python bindings from the canonical proto under the monorepo root.
# Source of truth: ../../../proto/vested/v1/connector_hub.proto

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$HERE/.."
PROTO_ROOT="$ROOT/../../proto"

if [ ! -f "$PROTO_ROOT/vested/v1/connector_hub.proto" ]; then
    echo "ERROR: proto file not found at $PROTO_ROOT/vested/v1/connector_hub.proto"
    exit 1
fi

mkdir -p "$ROOT/src/vested_connect/proto"

python -m grpc_tools.protoc \
    -I "$PROTO_ROOT" \
    --python_out="$ROOT/src/vested_connect/proto" \
    --grpc_python_out="$ROOT/src/vested_connect/proto" \
    --pyi_out="$ROOT/src/vested_connect/proto" \
    "$PROTO_ROOT/vested/v1/connector_hub.proto"

# grpc_tools writes vested/v1/* relative to the proto root; flatten so the
# import path is `vested_connect.proto.connector_hub_pb2` (no nested package).
if [ -d "$ROOT/src/vested_connect/proto/vested" ]; then
    mv "$ROOT/src/vested_connect/proto/vested/v1/"*.py  "$ROOT/src/vested_connect/proto/"
    mv "$ROOT/src/vested_connect/proto/vested/v1/"*.pyi "$ROOT/src/vested_connect/proto/" 2>/dev/null || true
    rm -rf "$ROOT/src/vested_connect/proto/vested"
fi

# Rewrite imports to the local package layout.
for f in "$ROOT/src/vested_connect/proto/"*.py; do
    python3 -c "
import re, sys, pathlib
p = pathlib.Path(sys.argv[1])
s = p.read_text()
s = re.sub(r'from vested\.v1 import (\w+)_pb2', r'from . import \1_pb2', s)
s = re.sub(r'import vested\.v1\.(\w+)_pb2', r'from . import \1_pb2', s)
p.write_text(s)
" "$f"
done

echo "Generated proto bindings in src/vested_connect/proto/"
