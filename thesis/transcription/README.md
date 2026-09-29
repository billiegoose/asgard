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
pdftoppm -f 15 -l 16 -r 220 -png ../../Hilton_AAI9111882.pdf build/source-pages/chapter1
```


## Visual audit

The full source PDF (pages 1–121, including front matter and back matter) has
been reviewed page by page against this transcription. The audit corrected
mathematical notation, omitted text, code indentation, and figure crops, and
reworked equation alignment and page breaks. The layout remains an 11-point
book on letter paper with 1.25-inch margins. Source-page comments refer to the
original PDF; the rebuilt document has different pagination.

All figures, including graph diagrams, machine diagrams, and compiler/rule
figures, are now rendered with native LaTeX and vector graphics. Earlier
scanned crops remain available as references. Apparent errors in the original
mathematics are preserved and documented in nearby source comments.

Transcription conventions and future audit guidance are in the repository's
`AGENTS.md`.
