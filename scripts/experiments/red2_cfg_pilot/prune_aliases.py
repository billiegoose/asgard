"""Remove unused, single-definition pure local aliases before ownership proof."""

import ast
from collections import Counter


def prune(fn):
    removed = []
    while True:
        loads = Counter(
            n.id
            for n in ast.walk(fn)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
        )
        stores = Counter(
            n.id
            for n in ast.walk(fn)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
        )
        drop = [
            n
            for n in fn.body
            if isinstance(n, ast.AnnAssign)
            and isinstance(n.target, ast.Name)
            and n.value is not None
            and isinstance(n.annotation, ast.Name)
            and not loads[n.target.id]
            and stores[n.target.id] == 1
            and not any(
                isinstance(
                    x,
                    (
                        ast.Call,
                        ast.NamedExpr,
                        ast.Await,
                        ast.Yield,
                        ast.YieldFrom,
                        ast.comprehension,
                        ast.Div,
                        ast.FloorDiv,
                        ast.Mod,
                        ast.Pow,
                    ),
                )
                for x in ast.walk(n.value)
            )
        ]
        if not drop:
            return removed
        ids = {id(n) for n in drop}
        removed += [n.target.id for n in drop]
        fn.body = [n for n in fn.body if id(n) not in ids]
