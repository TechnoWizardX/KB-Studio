#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUTPUT="dist"
NO_CACHE=()
BUILD_ARGS=()

usage() {
    cat <<'EOF'
Usage: scripts/build-linux.sh [options]

Build dist/KB-Studio on Ubuntu 22.04 (glibc 2.35) with Docker.

Options:
  --no-cache           rebuild all Docker layers
  --output DIR         output directory (default: dist)
  --glibc-max VERSION  fail if the bundle needs a newer glibc (default: 2.35)
  -h, --help           show this help
EOF
}

while (($#)); do
    case "$1" in
        --no-cache)
            NO_CACHE+=(--no-cache)
            shift
            ;;
        --output)
            [ $# -ge 2 ] || { echo "error: --output needs a directory" >&2; exit 2; }
            OUTPUT="$2"
            shift 2
            ;;
        --glibc-max)
            [ $# -ge 2 ] || { echo "error: --glibc-max needs a version" >&2; exit 2; }
            BUILD_ARGS+=(--build-arg "GLIBC_MAX=$2")
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "error: unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if ! command -v docker >/dev/null 2>&1; then
    echo "error: docker not found" >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "error: cannot access the Docker daemon" >&2
    echo "Add your user to the docker group and log in again:" >&2
    echo "  sudo usermod -aG docker \$USER" >&2
    exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "Building KB-Studio (Ubuntu 22.04, glibc 2.35)..." >&2
DOCKER_BUILDKIT=1 docker build \
    -f Dockerfile.build \
    --output "type=local,dest=$tmp" \
    "${NO_CACHE[@]}" \
    "${BUILD_ARGS[@]}" \
    .

binary="$tmp/KB-Studio"
if [ ! -x "$binary" ]; then
    echo "error: the build did not produce KB-Studio" >&2
    exit 1
fi

mkdir -p "$OUTPUT"
mv -f "$binary" "$OUTPUT/KB-Studio"

echo
echo "Built $OUTPUT/KB-Studio"
ls -lh "$OUTPUT/KB-Studio"
sha256sum "$OUTPUT/KB-Studio"

if [ -x .venv/bin/python ] && .venv/bin/python -c 'import PyInstaller' >/dev/null 2>&1; then
    .venv/bin/python scripts/check-glibc.py "$OUTPUT/KB-Studio"
fi
