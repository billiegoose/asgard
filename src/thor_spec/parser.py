from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Never

from thor_spec.ast import (
    App,
    Binding,
    Char,
    Definition,
    Expr,
    Float,
    Integer,
    Lambda,
    LetRec,
    Program,
    StructDef,
    StructLit,
    Symbol,
    TopLevel,
)


class ParseError(ValueError):
    """Raised when source text is not well-formed THOR syntax."""


class TokenKind(StrEnum):
    ATOM = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    BAR = auto()
    EQUALS = auto()
    STRUCTDEF = auto()
    NEWLINE = auto()


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    text: str
    line: int
    column: int


_INTEGER_RE = re.compile(r"[+-]?\d+")
_FLOAT_RE = re.compile(
    r"[+-]?(?:(?:\d+\.\d*)|(?:\d*\.\d+))(?:[eE][+-]?\d+)?|[+-]?\d+[eE][+-]?\d+"
)
_DELIMITERS = set("(){}[]|=")


def parse_expr(source: str) -> Expr:
    """Parse one THOR expression from source text."""
    parser = Parser(tuple(tokenize(source)))
    expr = parser.parse_expr()
    parser.skip_newlines()
    if not parser.at_end:
        parser.fail(parser.peek(), "unexpected token after expression")
    return expr


def parse_program(source: str) -> Program:
    """Parse top-level definitions, structure declarations, and expressions."""
    parser = Parser(tuple(tokenize(source)))
    forms: list[TopLevel] = []
    while True:
        parser.skip_newlines()
        if parser.at_end:
            break

        first = parser.peek()
        assert first is not None
        second = parser.peek(1)
        if first.kind is TokenKind.ATOM and second is not None:
            if second.kind is TokenKind.EQUALS:
                name = parser.consume(TokenKind.ATOM).text
                parser.consume(TokenKind.EQUALS)
                forms.append(Definition(name, parser.parse_expr()))
                continue
            if second.kind is TokenKind.STRUCTDEF:
                tag = parser.consume(TokenKind.ATOM).text
                parser.consume(TokenKind.STRUCTDEF)
                accessors: list[str] = []
                while not parser.at_end:
                    token = parser.peek()
                    assert token is not None
                    if token.kind is TokenKind.NEWLINE:
                        break
                    accessors.append(parser.consume(TokenKind.ATOM).text)
                forms.append(StructDef(tag, tuple(accessors)))
                continue

        forms.append(parser.parse_expr())
    return Program(tuple(forms))


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    line = 1
    column = 1
    index = 0
    while index < len(source):
        char = source[index]
        if char in " \t\r\f\v":
            index += 1
            column += 1
            continue
        if char == "\n":
            tokens.append(Token(TokenKind.NEWLINE, char, line, column))
            index += 1
            line += 1
            column = 1
            continue
        if char == ";" or (char == "#" and not source.startswith("#\\", index)):
            while index < len(source) and source[index] != "\n":
                index += 1
                column += 1
            continue
        if char == "=" and source.startswith("==", index):
            tokens.append(Token(TokenKind.EQUALS, "==", line, column))
            index += 2
            column += 2
            continue
        if char == "|" and source.startswith("|=", index):
            tokens.append(Token(TokenKind.STRUCTDEF, "|=", line, column))
            index += 2
            column += 2
            continue
        single = _single_token(char)
        if single is not None:
            tokens.append(Token(single, char, line, column))
            index += 1
            column += 1
            continue

        start = index
        start_column = column
        while index < len(source):
            current = source[index]
            if current.isspace() or current in _DELIMITERS or current == ";":
                break
            if current == "#" and not source.startswith("#\\", index):
                break
            index += 1
            column += 1
        if start == index:
            msg = f"unexpected character {char!r} at {line}:{column}"
            raise ParseError(msg)
        tokens.append(Token(TokenKind.ATOM, source[start:index], line, start_column))
    return tokens


def _single_token(char: str) -> TokenKind | None:
    return {
        "(": TokenKind.LPAREN,
        ")": TokenKind.RPAREN,
        "{": TokenKind.LBRACE,
        "}": TokenKind.RBRACE,
        "[": TokenKind.LBRACKET,
        "]": TokenKind.RBRACKET,
        "|": TokenKind.BAR,
        "=": TokenKind.ATOM,
    }.get(char)


class Parser:
    def __init__(self, tokens: tuple[Token, ...]) -> None:
        self._tokens = tokens
        self._position = 0

    @property
    def at_end(self) -> bool:
        return self._position >= len(self._tokens)

    def peek(self, offset: int = 0) -> Token | None:
        position = self._position + offset
        if position >= len(self._tokens):
            return None
        return self._tokens[position]

    def consume(self, kind: TokenKind) -> Token:
        token = self.peek()
        if token is None:
            msg = f"expected {kind.value}, found end of input"
            raise ParseError(msg)
        if token.kind is not kind:
            self.fail(token, f"expected {kind.value}")
        self._position += 1
        return token

    def skip_newlines(self) -> None:
        while not self.at_end:
            token = self.peek()
            assert token is not None
            if token.kind is not TokenKind.NEWLINE:
                break
            self._position += 1

    def parse_expr(self) -> Expr:
        self.skip_newlines()
        token = self.peek()
        if token is None:
            msg = "expected expression, found end of input"
            raise ParseError(msg)
        if token.kind is TokenKind.ATOM:
            self._position += 1
            return _atom_expr(token.text)
        if token.kind is TokenKind.LPAREN:
            return self.parse_paren_form()
        if token.kind is TokenKind.LBRACE:
            return self.parse_struct()
        if token.kind is TokenKind.LBRACKET:
            return self.parse_list_sugar()
        self.fail(token, "expected expression")

    def parse_paren_form(self) -> Expr:
        self.consume(TokenKind.LPAREN)
        self.skip_newlines()
        first = self.peek()
        if _is_atom(first, "LAMBDA"):
            self._position += 1
            return self.parse_lambda_tail()
        if _is_atom(first, "LETREC"):
            self._position += 1
            return self.parse_letrec_tail()

        items: list[Expr] = []
        while True:
            self.skip_newlines()
            token = self.peek()
            if token is None:
                msg = "unterminated parenthesized form"
                raise ParseError(msg)
            if token.kind is TokenKind.RPAREN:
                self._position += 1
                break
            items.append(self.parse_expr())
        return App(tuple(items))

    def parse_lambda_tail(self) -> Lambda:
        self.consume(TokenKind.LPAREN)
        params: list[str] = []
        while True:
            self.skip_newlines()
            token = self.peek()
            if token is None:
                msg = "unterminated LAMBDA parameter list"
                raise ParseError(msg)
            if token.kind is TokenKind.RPAREN:
                self._position += 1
                break
            params.append(self.consume(TokenKind.ATOM).text)
        body = self.parse_body_until(TokenKind.RPAREN, "LAMBDA")
        return Lambda(tuple(params), body)

    def parse_letrec_tail(self) -> LetRec:
        self.consume(TokenKind.LPAREN)
        bindings: list[Binding] = []
        while True:
            self.skip_newlines()
            token = self.peek()
            if token is None:
                msg = "unterminated LETREC binding list"
                raise ParseError(msg)
            if token.kind is TokenKind.RPAREN:
                self._position += 1
                break
            self.consume(TokenKind.LPAREN)
            name = self.consume(TokenKind.ATOM).text
            expr = self.parse_expr()
            self.skip_newlines()
            self.consume(TokenKind.RPAREN)
            bindings.append(Binding(name, expr))
        body = self.parse_body_until(TokenKind.RPAREN, "LETREC")
        return LetRec(tuple(bindings), body)

    def parse_body_until(self, end_kind: TokenKind, form_name: str) -> Expr:
        expressions: list[Expr] = []
        while True:
            self.skip_newlines()
            token = self.peek()
            if token is None:
                msg = f"unterminated {form_name} form"
                raise ParseError(msg)
            if token.kind is end_kind:
                self._position += 1
                break
            expressions.append(self.parse_expr())
        if not expressions:
            msg = f"{form_name} requires a body expression"
            raise ParseError(msg)
        if len(expressions) == 1:
            return expressions[0]
        return App(tuple(expressions))

    def parse_struct(self) -> StructLit:
        self.consume(TokenKind.LBRACE)
        self.skip_newlines()
        tag = self.consume(TokenKind.ATOM).text
        fields: list[Expr] = []
        while True:
            self.skip_newlines()
            token = self.peek()
            if token is None:
                msg = "unterminated structure literal"
                raise ParseError(msg)
            if token.kind is TokenKind.RBRACE:
                self._position += 1
                break
            fields.append(self.parse_expr())
        return StructLit(tag, tuple(fields))

    def parse_list_sugar(self) -> Expr:
        self.consume(TokenKind.LBRACKET)
        items: list[Expr] = []
        tail: Expr = Symbol("NIL")
        while True:
            self.skip_newlines()
            token = self.peek()
            if token is None:
                msg = "unterminated list literal"
                raise ParseError(msg)
            if token.kind is TokenKind.RBRACKET:
                self._position += 1
                break
            if token.kind is TokenKind.BAR:
                if not items:
                    self.fail(token, "dotted list requires a head expression")
                self._position += 1
                tail = self.parse_expr()
                self.skip_newlines()
                self.consume(TokenKind.RBRACKET)
                break
            items.append(self.parse_expr())
        return _pair_chain(items, tail)

    def fail(self, token: Token | None, message: str) -> Never:
        if token is None:
            raise ParseError(message)
        msg = f"{message} at {token.line}:{token.column}: {token.text!r}"
        raise ParseError(msg)


def _is_atom(token: Token | None, text: str) -> bool:
    return token is not None and token.kind is TokenKind.ATOM and token.text == text


def _atom_expr(text: str) -> Expr:
    if _INTEGER_RE.fullmatch(text):
        return Integer(int(text))
    if _FLOAT_RE.fullmatch(text):
        return Float(float(text))
    if text.startswith("#\\"):
        value = text[2:]
        if not value:
            msg = "character literal requires a value"
            raise ParseError(msg)
        return Char(_decode_char(value))
    return Symbol(text)


def _decode_char(value: str) -> str:
    names = {"space": " ", "newline": "\n", "tab": "\t"}
    return names.get(value.lower(), value)


def _pair_chain(items: list[Expr], tail: Expr) -> Expr:
    result = tail
    for item in reversed(items):
        result = StructLit("PAIR", (item, result))
    return result
