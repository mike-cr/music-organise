#!/usr/bin/env sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
build_dir=$(mktemp -d "${TMPDIR:-/tmp}/music-organise-pkgbuild.XXXXXX")

cleanup() {
  rm -rf "$build_dir"
}
trap cleanup EXIT INT TERM

cp "$repo_root/PKGBUILD" "$build_dir/"
cd "$build_dir"

if command -v yay >/dev/null 2>&1; then
  yay -Bi .
else
  makepkg -si
fi
