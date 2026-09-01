from __future__ import annotations

from dataclasses import dataclass

from thor_engine.golden import run_source
from thor_lang.ast import (
    App,
    Binding,
    Block,
    Char,
    Expr,
    Float,
    Integer,
    Lambda,
    LetRec,
    Rec,
    StructLit,
    Symbol,
    Var,
)
from thor_lang.parser import ParseError, parse_expr
from thor_lang.pretty import to_source


@dataclass(frozen=True, slots=True)
class ParitySnapshot:
    quantum: int
    thor: str
    red2: str
    matches: bool


@dataclass(frozen=True, slots=True)
class ParityResult:
    max_quantum: int
    snapshots: tuple[ParitySnapshot, ...]

    @property
    def first_mismatch(self) -> ParitySnapshot | None:
        return next(
            (snapshot for snapshot in self.snapshots if not snapshot.matches),
            None,
        )

    @property
    def final_snapshot(self) -> ParitySnapshot | None:
        if not self.snapshots:
            return None
        return self.snapshots[-1]

    @property
    def mismatch_ranges(self) -> tuple[tuple[int, int], ...]:
        ranges: list[tuple[int, int]] = []
        start: int | None = None
        previous: int | None = None
        for snapshot in self.snapshots:
            if not snapshot.matches:
                if start is None:
                    start = snapshot.quantum
                previous = snapshot.quantum
                continue
            if start is not None and previous is not None:
                ranges.append((start, previous))
                start = None
                previous = None
        if start is not None and previous is not None:
            ranges.append((start, previous))
        return tuple(ranges)

    @property
    def first_reconvergence(self) -> ParitySnapshot | None:
        mismatch = self.first_mismatch
        if mismatch is None:
            return None
        return next(
            (
                snapshot
                for snapshot in self.snapshots
                if snapshot.quantum > mismatch.quantum and snapshot.matches
            ),
            None,
        )


def compare_prefixes(source: str, *, max_quantum: int) -> ParityResult:
    if max_quantum < 0:
        msg = f"max_quantum must be non-negative, got {max_quantum}"
        raise ValueError(msg)
    snapshots = tuple(
        _snapshot(source, quantum=quantum) for quantum in range(max_quantum + 1)
    )
    return ParityResult(max_quantum=max_quantum, snapshots=snapshots)


def _snapshot(source: str, *, quantum: int) -> ParitySnapshot:
    thor = run_source(source, model="thor", quantum=quantum)
    red2 = run_source(source, model="red2", quantum=quantum)
    return ParitySnapshot(
        quantum=quantum,
        thor=thor,
        red2=red2,
        matches=_canonical_output(thor) == _canonical_output(red2),
    )


def format_mismatch_report(result: ParityResult) -> str:
    """Return the detailed parity mismatch report used by CLI/task wrappers."""
    snapshots = {snapshot.quantum: snapshot for snapshot in result.snapshots}
    lines: list[str] = []
    for start, end in result.mismatch_ranges:
        mismatch = snapshots[start]
        lines.append(f"parity mismatch at quantum {start}")
        lines.append(f"thor: {mismatch.thor}")
        lines.append(f"red2: {mismatch.red2}")
        reconverged = snapshots.get(end + 1)
        if reconverged is not None and reconverged.matches:
            lines.append(f"parity reconverged at quantum {reconverged.quantum}")
        else:
            lines.append(f"parity did not reconverge by quantum {result.max_quantum}")
        lines.append("")
    return "\n".join(lines)


def _canonical_output(output: str) -> str:
    """Render output with bound names and RED2 ``(VAR n)`` forms alpha-normalized."""
    if not output:
        return output
    lines: list[str] = []
    for line in output.splitlines():
        try:
            lines.append(to_source(_canonical_expr(parse_expr(line), ())))
        except ParseError:
            lines.append(line)
    return "\n".join(lines)


def _canonical_expr(expr: Expr, scope: tuple[str, ...]) -> Expr:
    if isinstance(expr, Var | Integer | Float | Char | Block | Rec):
        return expr
    if isinstance(expr, Symbol):
        if expr.name in scope:
            return Var(scope.index(expr.name))
        return expr
    if isinstance(expr, Lambda):
        return Lambda(expr.params, _canonical_expr(expr.body, expr.params + scope))
    if isinstance(expr, App):
        var = _red2_var_form(expr)
        if var is not None:
            return var
        return App(tuple(_canonical_expr(item, scope) for item in expr.items))
    if isinstance(expr, LetRec):
        names = tuple(binding.name for binding in expr.bindings)
        binding_scope = names + scope
        return LetRec(
            tuple(
                Binding(binding.name, _canonical_expr(binding.expr, binding_scope))
                for binding in expr.bindings
            ),
            _canonical_expr(expr.body, binding_scope),
        )
    if isinstance(expr, StructLit):
        return StructLit(
            expr.tag,
            tuple(_canonical_expr(field, scope) for field in expr.fields),
        )
    return expr


def _red2_var_form(expr: App) -> Var | None:
    if (
        len(expr.items) == 2
        and isinstance(expr.items[0], Symbol)
        and expr.items[0].name == "VAR"
        and isinstance(expr.items[1], Integer)
    ):
        return Var(expr.items[1].value)
    return None
