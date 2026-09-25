from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Var:
    index: int
    name: str | None = None


@dataclass(frozen=True, slots=True)
class Lambda:
    params: tuple[str, ...]
    body: Expr


@dataclass(frozen=True, slots=True)
class App:
    items: tuple[Expr, ...]


@dataclass(frozen=True, slots=True)
class Binding:
    name: str
    expr: Expr


@dataclass(frozen=True, slots=True)
class LetRec:
    bindings: tuple[Binding, ...]
    body: Expr


@dataclass(frozen=True, slots=True)
class StructLit:
    tag: str
    fields: tuple[Expr, ...]


@dataclass(frozen=True, slots=True)
class Symbol:
    name: str


@dataclass(frozen=True, slots=True)
class Integer:
    value: int


@dataclass(frozen=True, slots=True)
class Float:
    value: float


@dataclass(frozen=True, slots=True)
class Char:
    value: str


@dataclass(frozen=True, slots=True)
class Block:
    expressions: tuple[Expr, ...]
    names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Rec:
    index: int
    store: tuple[object, ...]
    block: Block


Expr = (
    Var
    | Lambda
    | App
    | LetRec
    | StructLit
    | Symbol
    | Integer
    | Float
    | Char
    | Block
    | Rec
)


@dataclass(frozen=True, slots=True)
class Definition:
    name: str
    expr: Expr


@dataclass(frozen=True, slots=True)
class StructDef:
    tag: str
    accessors: tuple[str, ...]


TopLevel = Definition | StructDef | Expr


@dataclass(frozen=True, slots=True)
class Program:
    forms: tuple[TopLevel, ...]
