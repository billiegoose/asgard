# Agent Notes

- The source PDF is `Hilton_AAI9111882.pdf`; it is intentionally git-ignored.
- The LaTeX transcription lives in `thesis/transcription/`. Build it with
  `thesis/transcription/scripts/compile.sh`; Tectonic is installed and works.
- Keep `thesis/transcription/src/main.tex` aligned with the user's current
  layout baseline: `11pt` book class and `letterpaper,margin=1.25in`.
- OCR is useful only as a prose draft. Verify equations, Greek letters, arrows,
  primes, subscripts, and rule names visually against rendered source pages.
- Prefer ASCII LaTeX source commands such as `\lambda`, `\beta`, `\rho`, and
  `\longrightarrow` instead of literal Unicode math symbols.
- Keep transcription guidance in this file rather than a separate notes file.
- Keep chapter commits focused: one chapter per commit when possible.
- Do not write tests that prove success by waiting for a subprocess timeout. For
  long-running/infinite programs, wait until the expected output appears, then
  terminate the process explicitly.
- Front matter, Chapters 1 through 6, Appendix A, the bibliography, and
  biographical data are transcribed and committed. Chapter 2's graph figures
  share vector geometry in `thesis/transcription/src/assets/wadsworth-graph.tex`;
  the earlier scanned crops remain in the same directory for reference.
- Chapters 4 and 5 have native diagrams in
  `src/assets/chapter4/figure-4-*.tex` and `src/assets/chapter5/figure-5-*.tex`
  relative to the transcription directory. Their matching PNGs are reference
  crops; edit the included `.tex` files to change the rendered diagrams.
- Preserve hollow and filled instruction head bits in the Chapter 5 diagrams;
  these circles carry meaning and are distinct from pointer dots.

- Semantic rules in the original put conclusions above premises. Use
  `\semanticrule` to retain this order and keep premises at full text size.
- Preserve apparent inconsistencies in the original mathematics and record
  them in nearby LaTeX comments rather than silently correcting the author.
- Keep individual code examples/procedures together when they fit on a page;
  check the rendered PDF after changing equation alignment or figure crops.
