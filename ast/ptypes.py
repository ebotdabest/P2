def auto_str(cls):
    def __str__(self):
        class_name = self.__class__.__name__
        attrs = ', '.join(f"{key}={str(value)!r}" for key, value in self.__dict__.items())
        return f"{class_name}({attrs})"

    cls.__str__ = __str__
    return cls

@auto_str
class Constant:
    def __init__(self, value, tpe):
        self.value = value
        self.tpe = tpe

@auto_str
class VariableReference:
    def __init__(self, var):
        self.var = var

@auto_str
class FunctionDefinition:
    def __init__(self, func_name, args, statements, return_type):
        self.func_name = func_name
        self.args = args
        self.return_type = return_type
        self.statements = statements


@auto_str
class FuncCall:
    def __init__(self, name, args):
        self.name = name
        self.args = args

@auto_str
class FuncArg:
    def __init__(self, name, tpe):
        self.name = name
        self.tpe = tpe

@auto_str
class FuncDefaultArg:
    def __init__(self, name, tpe, default):
        self.name = name
        self.tpe = tpe
        self.default = default

@auto_str
class VariableOp:
    def __init__(self, var, expression, op):
        self.var = var
        self.expression = expression
        self.op = op

@auto_str
class VariableCreation:
    def __init__(self, name, tpe, value):
        self.name = name
        self.tpe = tpe
        self.value = value

@auto_str
class VariableActions:
    def __init__(self, actions):
        self.actions = actions
        self.amount = len(actions)

    def var(self):
        return self.actions[0]

@auto_str
class ReturnStatement:
    def __init__(self, expression):
        self.expr = expression

@auto_str
class BinaryOp:
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right

@auto_str
class ConditionToken:
    def __init__(self, token):
        self.token = token

@auto_str
class IfStatement:
    def __init__(self, expr, block, elifs, else_block):
        self.expr = expr
        self.block = block
        self.elifs = elifs
        self.else_block = else_block

@auto_str
class ElifBlock:
    def __init__(self, expr, block):
        self.expr = expr
        self.block = block

@auto_str
class ImportStmt:
    def __init__(self, func_name, args, return_type):
        self.func_name = func_name
        self.args = args
        self.return_type = return_type


class VAArgs:
    pass

@auto_str
class GlobalStmt:
    def __init__(self, symbol_names):
        self.names = symbol_names

@auto_str
class TernaryOp:
    def __init__(self, cond, true, false):
        self.cond = cond
        self.true = true
        self.false = false

@auto_str
class UnaryOp:
    def __init__(self, pref, op):
        self.pref = pref
        self.op = op

@auto_str
class SliceOp:
    def __init__(self, var, slices):
        self.var = var
        self.slices = slices

def bool_maker(value):
    if value == "True":
        return 1
    elif value == "False":
        return 0
    else:
        return -1

def str_maker(value: str) -> list[int]:
    return [ord(char) for char in bytes(value, "utf-8").decode("unicode_escape")]

usable_types = {
    "int": int,
    "double": float,
    "float": float,
    "bool": bool_maker,
    "str": str_maker
}