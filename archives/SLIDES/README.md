# SLIDES

TeX source for **Michael L. Hilton's dissertation-defense slides** and supporting figures.

`DEF.TEX` opens with:

- **An Architecture for Declarative Programming**
- **Dissertation Defense**
- **Michael L. Hilton**

and states the goal as developing a computing architecture to implement the complete lambda-beta calculus efficiently. Its outline explicitly includes **“Present RED2 Solutions”** and **“Assessment of the RED2 Architecture.”**

## Files

- `DEF.TEX` — main defense-slide content; the most important file here for understanding the thesis architecture at a high level.
- `SLIDES.TEX` — tiny slide document wrapper that includes/uses the defense material through the period slide tooling.
- `LAMBDA.TEX` — detailed machine-state figure(s), notably naming registers such as `fsp`, `env`, `pc`, `argcnt`, `prim`, and `fire`.
- `LGR1.TEX`, `LGR2.TEX` — graph-reduction diagrams.
- `TEXFONTS.SUB` — TeX/font setup artifact.

These files are evidence that the dissertation existed under the title “An Architecture for Declarative Programming,” but the dissertation manuscript's TeX itself is not present in the archive.
