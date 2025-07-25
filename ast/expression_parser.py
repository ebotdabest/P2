import re

from ast.ptypes import ConditionToken, Constant, VariableReference, BinaryOp, ExprStatement

CONDITIONS = [
    "==",
    "!=",
    ">=",
    "<=",
    ">",
    "<",
    "and",
    "or",
    "not",
    "in",
    "is"
]

OPERATORS = [
    "//",
    "/",
    "*",
    "-",
    "+",
    "%"
]

TOKENS = [
    *CONDITIONS,
    "(",
    ")",
    *OPERATORS
]

escaped_tokens = sorted(TOKENS, key=len, reverse=True)
escaped_tokens = [re.escape(tok) for tok in escaped_tokens]

token_pattern = '|'.join(escaped_tokens)
pattern = r""""""

def tokenize(source: str):
    tokens = []
    lexeme = ''
    i = 0

    while i < len(source):
        c = source[i]

        if c.isspace():
            if lexeme:
                tokens.append(lexeme)
                lexeme = ''
            i += 1
            continue

        if c == '"':
            if lexeme:
                tokens.append(lexeme)
                lexeme = ''
            end = i + 1
            while end < len(source) and source[end] != '"':
                end += 1
            if end < len(source):
                tokens.append(source[i:end+1])
                i = end + 1
            else:
                tokens.append(source[i:])
                i = len(source)
            continue

        matched = False
        for kw in sorted(TOKENS, key=len, reverse=True):
            if source.startswith(kw, i):
                if lexeme:
                    tokens.append(lexeme)
                    lexeme = ''
                tokens.append(kw)
                i += len(kw)
                matched = True
                break

        if matched:
            continue

        lexeme += c
        i += 1

    if lexeme:
        tokens.append(lexeme)

    return tokens

# Fuckass thing needed a parser
# This shit is barely held
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def get_token(self): return self.tokens[self.pos] if self.pos < len(self.tokens) else None
    def next_token(self):
        val = self.get_token()
        self.pos += 1
        return val

    def parse(self):
        expr = self.parse_expression()

        if self.get_token() in CONDITIONS:
            cond = self.next_token()
            right = self.parse_expression()
            return [expr, ConditionToken(cond), right]
        return [expr]

    def parse_expression(self, min_prec=0):
        left = self.parse_atom()

        while True:
            op = self.get_token()
            if op not in OPERATORS: break
            prec = self.pedma_size(op)
            if prec < min_prec: break
            self.next_token()
            right = self.parse_expression(prec + 1)
            left = BinaryOp(left, op, right)

        return left

    def parse_atom(self):
        tok = self.next_token()
        if isinstance(tok, str) and tok.startswith('"') and tok.endswith('"'):
            return Constant(tok[1:-1], "str")
        try:
            if "." in tok:
                return Constant(float(tok), "float")
            return Constant(int(tok), "int")
        except (ValueError, TypeError):
            if tok in TOKENS:
                raise ValueError(f"Unexpected token: {tok}")
            return VariableReference(tok)

    @staticmethod
    def pedma_size(op):
        if op in ["*", "/", "//"]: return 3
        if op in ["+", "-"]: return 2
        return 1

def parse_expression(expr):
    tokens = tokenize(expr)
    expr_ast = Parser(tokens).parse()
    return ExprStatement(expr_ast)