from __future__ import annotations

from collections.abc import Sequence
from math import ceil, floor
from operator import add, mod, mul, sub, truediv

from thor_spec.ast import (
    App,
    Char,
    Expr,
    Float,
    Integer,
    Lambda,
    LetRec,
    StructLit,
    Symbol,
    Var,
)
from thor_spec.red2.instructions import Instruction, Opcode

TRUE = Instruction(Opcode.PRIM_0, "TRUE", head=True)
FALSE = Instruction(Opcode.PRIM_0, "FALSE", head=True)


def register_struct_accessors(tag: str, accessors: tuple[str, ...]) -> tuple[str, ...]:
    """Register source-generated structure accessors as RED2 native selectors."""
    register_struct_arity(tag, len(accessors))
    names: list[str] = []
    for index, accessor in enumerate(accessors):
        for name in _struct_accessor_names(tag, accessor):
            _STRUCT_ACCESSORS[name] = (tag, index)
            names.append(name)
    return tuple(dict.fromkeys(names))


def register_struct_arity(tag: str, arity: int) -> None:
    """Teach RED2 result decompilation the field count for a source struct."""
    _STRUCT_ARITIES[tag] = arity


def struct_accessor(name: str) -> tuple[str, int] | None:
    """Return ``(tag, field_index)`` for a registered native selector name."""
    return _STRUCT_ACCESSORS.get(name)


def fire_primitive(
    name: str,
    args: tuple[Instruction, ...],
    quantum: int,
) -> tuple[Instruction | None, int]:
    """Fire one strict RED2 primitive over already-reduced instruction args.

    The returned quantum is decremented only when a primitive contraction occurs.
    Non-strict forms such as ``IF`` and structure selectors are handled by the
    machine because they need access to unreduced argument graph bodies.
    """
    if quantum <= 0:
        return None, quantum
    result = _fire_without_quantum(name, args)
    if result is None:
        return None, quantum
    return result, quantum - 1


def primitive_name(inst: Instruction) -> str | None:
    if inst.opcode in {
        Opcode.PRIM_0,
        Opcode.PRIM_1,
        Opcode.PRIM_2,
        Opcode.SYM,
    } and isinstance(
        inst.data,
        str,
    ):
        return inst.data
    return None


def instructions_to_expr(instructions: Sequence[Instruction]) -> Expr:
    """Decompile the RED2 result graph emitted by :class:`Red2Machine`."""
    if not instructions:
        return Symbol("PNP")
    reader = _InstructionReader(tuple(instructions))
    return reader.parse_expr()


def expr_to_instruction(expr: Expr) -> Instruction | None:
    if isinstance(expr, Integer):
        return Instruction(Opcode.INT, expr.value, head=True)
    if isinstance(expr, Float):
        return Instruction(Opcode.FLOAT, expr.value, head=True)
    if isinstance(expr, Char):
        return Instruction(Opcode.CHAR, expr.value, head=True)
    if isinstance(expr, Symbol):
        if expr.name in {"TRUE", "FALSE", "NIL"}:
            return Instruction(Opcode.PRIM_0, expr.name, head=True)
        return Instruction(Opcode.SYM, expr.name, head=True)
    return None


def instruction_to_expr(inst: Instruction) -> Expr | None:
    if inst.opcode is Opcode.INT and isinstance(inst.data, int):
        return Integer(inst.data)
    if inst.opcode is Opcode.FLOAT and isinstance(inst.data, float):
        return Float(inst.data)
    if inst.opcode is Opcode.CHAR and isinstance(inst.data, str):
        return Char(inst.data)
    if inst.opcode in {
        Opcode.SYM,
        Opcode.PRIM_0,
        Opcode.PRIM_1,
        Opcode.PRIM_2,
    } and isinstance(
        inst.data,
        str,
    ):
        return Symbol(inst.data)
    if inst.opcode is Opcode.VAR and isinstance(inst.data, int):
        return Var(inst.data)
    if inst.opcode is Opcode.VAR and isinstance(inst.data, str):
        return Var(0, inst.data)
    return None


def _fire_without_quantum(
    name: str, args: tuple[Instruction, ...]
) -> Instruction | None:
    if name in _BINARY_PRIMITIVES and len(args) == 2:
        return _fire_binary(name, args[0], args[1])
    if name == "NULL?" and len(args) == 1:
        return _fire_null(args[0])
    if name in _UNARY_PRIMITIVES and len(args) == 1:
        return _fire_unary(name, args[0])
    if name in _TYPE_PREDICATES and len(args) == 1:
        return TRUE if _predicate_matches(name, args[0]) else FALSE
    return None


def _fire_unary(name: str, arg: Instruction) -> Instruction | None:
    if name == "1-" and arg.opcode is Opcode.INT and isinstance(arg.data, int):
        return Instruction(Opcode.INT, arg.data - 1, head=True)
    value = _number_value(arg)
    if name == "1+" and value is not None:
        return _number_result(value + 1)
    if name == "MINUS" and value is not None:
        return _number_result(-value)
    if name == "ABS" and value is not None:
        return _number_result(abs(value))
    if name == "FLOOR" and value is not None:
        return Instruction(Opcode.INT, floor(value), head=True)
    if name == "CEILING" and value is not None:
        return Instruction(Opcode.INT, ceil(value), head=True)
    if name == "EVEN?" and arg.opcode is Opcode.INT and isinstance(arg.data, int):
        return TRUE if arg.data % 2 == 0 else FALSE
    if name == "NOT":
        if _is_true(arg):
            return FALSE
        if _is_false(arg):
            return TRUE
    return None


def _fire_null(arg: Instruction) -> Instruction | None:
    if _is_nil(arg):
        return TRUE
    if arg.opcode in {Opcode.APP, Opcode.VAR, Opcode.UBV}:
        return None
    return FALSE


def _fire_binary(
    name: str, left: Instruction, right: Instruction
) -> Instruction | None:
    if name in {"+", "-", "*", "/", "<", ">", "<=", ">=", "MOD"}:
        if left.opcode not in {Opcode.INT, Opcode.FLOAT} or right.opcode not in {
            Opcode.INT,
            Opcode.FLOAT,
        }:
            return None
        if not isinstance(left.data, int | float) or not isinstance(
            right.data, int | float
        ):
            return None
        if name == "<":
            return TRUE if left.data < right.data else FALSE
        if name == ">":
            return TRUE if left.data > right.data else FALSE
        if name == "<=":
            return TRUE if left.data <= right.data else FALSE
        if name == ">=":
            return TRUE if left.data >= right.data else FALSE
        if name == "MOD":
            if left.opcode is Opcode.INT and right.opcode is Opcode.INT:
                return Instruction(Opcode.INT, mod(left.data, right.data), head=True)
            return None
        if name == "/":
            value = truediv(left.data, right.data)
            if (
                left.opcode is Opcode.INT
                and right.opcode is Opcode.INT
                and value.is_integer()
            ):
                return Instruction(Opcode.INT, int(value), head=True)
            return Instruction(Opcode.FLOAT, float(value), head=True)
        op = {"+": add, "-": sub, "*": mul}[name]
        value = op(left.data, right.data)
        if left.opcode is Opcode.INT and right.opcode is Opcode.INT:
            return Instruction(Opcode.INT, int(value), head=True)
        return Instruction(Opcode.FLOAT, float(value), head=True)
    if name in {"EXPT", "MAX", "MIN"}:
        left_value = _number_value(left)
        right_value = _number_value(right)
        if left_value is None or right_value is None:
            return None
        if name == "EXPT":
            return _number_result(left_value**right_value)
        if name == "MAX":
            return _number_result(
                left_value if left_value >= right_value else right_value
            )
        return _number_result(left_value if left_value <= right_value else right_value)
    if name in {"=", "EQUAL?"}:
        left_expr = instruction_to_expr(left)
        right_expr = instruction_to_expr(right)
        if left_expr is None or right_expr is None:
            return None
        return TRUE if left_expr == right_expr else FALSE
    return None


def _number_value(inst: Instruction) -> int | float | None:
    if inst.opcode in {Opcode.INT, Opcode.FLOAT} and isinstance(inst.data, int | float):
        return inst.data
    return None


def _number_result(value: int | float) -> Instruction:
    if isinstance(value, float):
        if value.is_integer():
            return Instruction(Opcode.INT, int(value), head=True)
        return Instruction(Opcode.FLOAT, value, head=True)
    return Instruction(Opcode.INT, value, head=True)


def _predicate_matches(name: str, arg: Instruction) -> bool:
    return (
        (name == "INTEGER?" and arg.opcode is Opcode.INT)
        or (name == "FLOAT?" and arg.opcode is Opcode.FLOAT)
        or (name == "CHAR?" and arg.opcode is Opcode.CHAR)
        or (name == "SYMBOL?" and arg.opcode in {Opcode.SYM, Opcode.PRIM_0})
        or (name == "STRUCTURE?" and arg.opcode is Opcode.STRUCT)
    )


def _is_true(inst: Instruction) -> bool:
    return inst.opcode is Opcode.PRIM_0 and inst.data == "TRUE"


def _is_false(inst: Instruction) -> bool:
    return inst.opcode is Opcode.PRIM_0 and inst.data == "FALSE"


def _is_nil(inst: Instruction) -> bool:
    return inst.opcode is Opcode.PRIM_0 and inst.data == "NIL"


def _struct_accessor_names(tag: str, accessor: str) -> tuple[str, ...]:
    return (accessor, f"{tag}-{accessor}")


class _InstructionReader:
    def __init__(self, instructions: tuple[Instruction, ...]) -> None:
        self.instructions = instructions
        self.index = 0

    def parse_expr(self) -> Expr:
        if self.index >= len(self.instructions):
            return Symbol("PNP")
        inst = self.instructions[self.index]
        self.index += 1
        scalar = instruction_to_expr(inst)
        if scalar is not None:
            return scalar
        if inst.opcode is Opcode.APP:
            argc = inst.data if isinstance(inst.data, int) and inst.data > 0 else 1
            operator = self.parse_expr()
            args = tuple(self.parse_expr() for _ in range(argc))
            return App((operator, *args))
        if inst.opcode is Opcode.LAMBDA:
            param = inst.data if isinstance(inst.data, str) else str(inst.data)
            body = self.parse_expr()
            return Lambda((param,), body)
        if inst.opcode is Opcode.STRUCT:
            tag = inst.data if isinstance(inst.data, str) else str(inst.data)
            arity = _STRUCT_ARITIES.get(tag, 0)
            fields = tuple(self.parse_expr() for _ in range(arity))
            return StructLit(tag, fields)
        if inst.opcode is Opcode.RUP:
            count = inst.data if isinstance(inst.data, int) else 0
            bindings = []
            for _ in range(count):
                block = self.instructions[self.index]
                self.index += 1
                name = block.data if isinstance(block.data, str) else str(block.data)
                bindings.append((name, self.parse_expr()))
            body = self.parse_expr()
            from thor_spec.ast import Binding

            return LetRec(tuple(Binding(name, expr) for name, expr in bindings), body)
        return Symbol(inst.opcode.name)


_BINARY_PRIMITIVES = {
    "+",
    "-",
    "*",
    "/",
    "<",
    ">",
    "<=",
    ">=",
    "=",
    "EQUAL?",
    "EXPT",
    "MAX",
    "MIN",
    "MOD",
}
_UNARY_PRIMITIVES = {
    "1-",
    "1+",
    "ABS",
    "CEILING",
    "EVEN?",
    "FLOOR",
    "MINUS",
    "NOT",
    "NULL?",
}
_TYPE_PREDICATES = {"INTEGER?", "FLOAT?", "CHAR?", "SYMBOL?", "STRUCTURE?"}
_STRUCT_ARITIES = {"PAIR": 2}
_STRUCT_ACCESSORS: dict[str, tuple[str, int]] = {}
register_struct_accessors("PAIR", ("CAR", "CDR"))
