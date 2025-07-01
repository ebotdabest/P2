from ast.gen.PythonParser import PythonParser
from ast.gen.PythonParserVisitor import PythonParserVisitor
from ast.ptypes import *
from errors import NoTypeError, SymbolNotFound
from antlr4.tree.Tree import TerminalNodeImpl
import re

class CurrentReader:
    def __init__(self):
        self.value = None

class P2Visitor(PythonParserVisitor):
    def __init__(self):
        super().__init__()
        self.statements = []
        self.send_to_reader = None

        self.scope = {}

    def read_result(self):
        return self.statements

    def create_reader(self, reader):
        def send(value):
            reader.value = value

        return send


    def send_to_top(self, stmt):
        self.statements.append(stmt)


    def visitFunction_def_raw(self, ctx: PythonParser.Function_def_rawContext):
        func_name = ctx.name().getText()
        return_type = None
        for i, c in enumerate(ctx.children):
            if c.getText() == "->":
                return_type = ctx.getChild(i + 1).getText()
                break


        args = []
        params = ctx.params()
        if params:
            params = params.parameters()
            for p in params.param_no_default():
                if not p.param().annotation():
                    raise NoTypeError(p.param().name().getText())
                tpe = self.visit(p.param().annotation()).var
                name = p.param().name().getText()
                args.append(FuncArg(name, tpe))

            for p in params.param_with_default():
                if not p.param().annotation():
                    raise NoTypeError(p.param().name().getText())

                tpe = p.param().annotation().getText()
                name = p.param().name().getText()
                default = p.default_assignment()
                default = self.visit(default)
                args.append(FuncDefaultArg(name, tpe, default))

        statements = []
        body = ctx.block().statements().statement()
        for stmt in body:
            reader = CurrentReader()
            self.send_to_reader = self.create_reader(reader)
            self.visit(stmt)
            statements.append(reader.value)
            self.send_to_reader = None

        func = FunctionDefinition(func_name, args, statements, return_type)
        self.statements.append(func)

    def visitAssignment(self, ctx:PythonParser.AssignmentContext):
        name = ctx.children[0]
        if isinstance(name, PythonParser.Star_targetsContext):
            action = ctx.children[1]
            value = self.visit(ctx.children[2])

            self.send_to_reader(VariableOp(name.getText(), value, action.getText()))

        if isinstance(name, PythonParser.NameContext):
            tpe = ctx.children[2].getText()
            value = self.visit(ctx.children[4])

            self.scope[name.getText()] = VariableCreation(name.getText(), tpe, value)
            if self.send_to_reader:
                self.send_to_reader(VariableCreation(name.getText(), tpe, value))
            else:
                self.send_to_top(VariableCreation(name.getText(), tpe, value))

    def visitReturn_stmt(self, ctx:PythonParser.Return_stmtContext):
        self.send_to_reader(ReturnStatement(self.visit(ctx.star_expressions())))


    def visitPrimary(self, ctx:PythonParser.PrimaryContext):
        if len(ctx.children) >= 3 and ctx.children[1].getText() == "(" and ctx.children[-1].getText() == ")":
            func_name = ctx.children[0].getText()
            args = []
            if ctx.arguments():
                for expr in ctx.arguments().args().expression():
                    value = self.visit(expr)
                    args.append(value)
            sent = FuncCall(func_name, args)
            self.send_to_reader(FuncCall(func_name, args))
            return sent

        for c in ctx.atom().children:
            if isinstance(c, PythonParser.StringsContext):
                return Constant(c.string(0).getText()[1:-1], 'str')
            else:
                value: str = c.getText()
                as_bool = usable_types["bool"](value)
                if as_bool != -1:
                    return Constant(value, "bool")

                if any(char.isalpha() for char in value):
                    return VariableReference(value)
                parent = ctx.parentCtx
                while parent.parentCtx and type(parent) != PythonParser.AssignmentContext:
                    parent = parent.parentCtx

                if isinstance(parent, PythonParser.File_inputContext):
                    parent = ctx.parentCtx
                    while parent.parentCtx and type(parent) != PythonParser.Function_def_rawContext:
                        parent = parent.parentCtx
                    tpe = None
                    for i, c in enumerate(parent.children):
                        if c.getText() == "->":
                            tpe = self.visit(parent.children[i + 1]).var
                else:
                    if len(parent.children) == 3:
                        var_name = parent.children[0].getText()
                        if var_name not in self.scope.keys():
                            raise SymbolNotFound(var_name)
                        tpe = self.scope[var_name].tpe
                    else:
                        tpe = parent.children[2].getText()

                return Constant(value, tpe)

        return self.visitChildren(ctx)

    def visitSum(self, ctx: PythonParser.SumContext):
        if len(ctx.children) == 1:
            return self.visit(ctx.children[0])

        left = self.visit(ctx.children[0])
        i = 1
        while i < len(ctx.children) - 1:
            op = ctx.children[i].getText()
            right = self.visit(ctx.children[i + 1])
            left = BinaryOp(left, op, right)
            i += 2
        return left

    def visitTerm(self, ctx: PythonParser.TermContext):
        if len(ctx.children) == 1:
            return self.visit(ctx.children[0])

        left = self.visit(ctx.children[0])
        i = 1
        while i < len(ctx.children) - 1:
            op = ctx.children[i].getText()
            right = self.visit(ctx.children[i + 1])
            left = BinaryOp(left, op, right)
            i += 2
        return left

    def visitFactor(self, ctx: PythonParser.FactorContext):
        return self.visit(ctx.power())

    def visitPower(self, ctx: PythonParser.PowerContext):
        return self.visit(ctx.await_primary())

    def visitIf_stmt(self, ctx:PythonParser.If_stmtContext):
        expr = self.visit(ctx.children[1])
        statements = self.visit(ctx.children[3])
        elif_blocks = []
        else_block = []
        for c in ctx.children[3:]:
            if isinstance(c, PythonParser.Elif_stmtContext):
                chain_complex = self.visit(c)
                flat = self.flatten(chain_complex)
                elif_blocks = flat[0:-1]
                else_block = flat[-1]
            if isinstance(c, PythonParser.Else_blockContext):
                else_block = self.visit(c)
        statement = IfStatement(expr, statements, elif_blocks, else_block)
        self.send_to_reader(statement)
        return statement

    def visitBlock(self, ctx:PythonParser.BlockContext):
        statements = []
        for c in ctx.children:
            if not isinstance(c, PythonParser.StatementsContext): continue
            reader = CurrentReader()
            old_send = self.send_to_reader
            self.send_to_reader = self.create_reader(reader)
            self.visit(c)
            self.send_to_reader = old_send
            statements.append(reader.value)

        return statements

    def visitElif_stmt(self, ctx:PythonParser.Elif_stmtContext):
        expr = self.visit(ctx.children[1])
        block = self.visit(ctx.children[3])

        last = self.visit(ctx.children[-1])
        return ElifBlock(expr, block), last

    def visitElse_block(self, ctx:PythonParser.Else_blockContext):
        return self.visit(ctx.block())

    def visitNamed_expression(self, ctx:PythonParser.Named_expressionContext):
        tokens = [
            "==",
            ">=",
            "<=",
            ">",
            "<",
            "or",
            "and",
            "(",
            ")"
        ]

        tokens_sorted = sorted(tokens, key=lambda x: -len(x))
        pattern = r'(' + '|'.join(re.escape(tok) for tok in tokens_sorted) + r')'

        spaced = re.sub(pattern, r' \1 ', ctx.getText())

        parts = []
        for part in spaced.strip().split():
            if part in tokens:
                parts.append(ConditionToken(part))
            else:
                as_bool = usable_types["bool"](part)
                if (part.startswith('"') and part.endswith('"')) or (part.startswith("'") and part.endswith("'")):
                    parts.append(Constant(part[1:-1], "str"))
                elif as_bool != -1:
                    parts.append(Constant(part, "bool"))
                elif "." in part:
                    parts.append(Constant(part, "float"))
                elif any(char.isalpha() for char in part):
                    parts.append(VariableReference(part))
                else:
                    parts.append(Constant(part, "int"))
        return parts

    def flatten(self, tup):
        flat = []
        while type(tup[1]) == tuple:
            flat.append(tup[0])
            tup = tup[1]

        flat.append(tup[0])
        flat.append(tup[1])

        return flat