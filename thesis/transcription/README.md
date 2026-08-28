# Hilton Thesis Transcription

This directory contains a modern LaTeX transcription of Michael Lee Hilton's
1990 dissertation, *Implementation of Declarative Languages*.

The source PDF is scanned from microfilm, so OCR is treated only as a hint. The
transcription should be checked visually against rendered page images from the
original PDF.

## Compile

macOS Preview can view PDFs, but it does not compile LaTeX source directly. Use
the compile script after installing one of `latexmk`, `tectonic`, or `pdflatex`:

```sh
./scripts/compile.sh
```

The output PDF is written to `build/main.pdf`.

## Source Page Images

Chapter 1 was transcribed from PDF pages 15-16:

```sh
pdftoppm -f 15 -l 16 -r 220 -png ../Hilton_AAI9111882.pdf build/source-pages/chapter1
```

