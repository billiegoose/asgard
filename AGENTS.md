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
  biographical data are transcribed and committed; Chapter 2 includes two
  cropped graph figures under `thesis/transcription/src/assets/`.
