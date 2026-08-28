#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(dirname "$SCRIPT_DIR")
SRC_DIR="$PROJECT_DIR/src"
BUILD_DIR="$PROJECT_DIR/build"

mkdir -p "$BUILD_DIR"
cd "$SRC_DIR"

if command -v latexmk >/dev/null 2>&1; then
  latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir="$BUILD_DIR" main.tex
elif command -v tectonic >/dev/null 2>&1; then
  tectonic --outdir "$BUILD_DIR" main.tex
elif command -v pdflatex >/dev/null 2>&1; then
  pdflatex -interaction=nonstopmode -halt-on-error -output-directory="$BUILD_DIR" main.tex
  pdflatex -interaction=nonstopmode -halt-on-error -output-directory="$BUILD_DIR" main.tex
else
  printf '%s\n' "No LaTeX compiler found."
  printf '%s\n' "Install MacTeX/BasicTeX for latexmk or pdflatex, or install tectonic."
  exit 1
fi

printf '%s\n' "Wrote $BUILD_DIR/main.pdf"
