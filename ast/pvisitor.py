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

        self.scope = {}

    def read_result(self):
        return self.statements


    def send_to_top(self, stmt):
        self.statements.append(stmt)

    def visitPower(self, ctx):
        return self.visit(ctx.await_primary())

    def visitFactor(self, ctx):
        return self.visit(ctx.power())

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
                default = self.visit(p.default_assignment())
                args.append(FuncDefaultArg(name, tpe, default))

        statements = []
        for stmt in ctx.block().statements().statement():
            result = self.visit(stmt)

            if result is not None:
                statements.append(result)

        func = FunctionDefinition(func_name, args, statements, return_type)
        self.statements.append(func)

    def visitAssignment(self, ctx: PythonParser.AssignmentContext):
        name = ctx.children[0]
        if isinstance(name, PythonParser.Star_targetsContext):
            action = ctx.children[1]
            value = self.visit(ctx.children[2])
            stmt = VariableOp(name.getText(), value, action.getText())
            return stmt

        if isinstance(name, PythonParser.NameContext):
            tpe = ctx.children[2].getText()
            value = self.visit(ctx.children[4])
            stmt = VariableCreation(name.getText(), tpe, value)
            self.scope[name.getText()] = stmt
            return stmt

    def visitReturn_stmt(self, ctx:PythonParser.Return_stmtContext):
        return ReturnStatement(self.visit(ctx.star_expressions()))


    def visitPrimary(self, ctx:PythonParser.PrimaryContext):
        if len(ctx.children) >= 3 and ctx.children[1].getText() == "(" and ctx.children[-1].getText() == ")":
            func_name = ctx.children[0].getText()
            args = []
            if ctx.arguments():
                for expr in ctx.arguments().args().expression():
                    value = self.visit(expr)
                    args.append(value)
            sent = FuncCall(func_name, args)
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


    def visitIf_stmt(self, ctx: PythonParser.If_stmtContext):
        expr = self.visit(ctx.children[1])
        statements = self.visit(ctx.children[3])

        elif_blocks = []
        else_block = []

        for c in ctx.children[3:]:
            if isinstance(c, PythonParser.Elif_stmtContext):
                chain_complex = self.visit(c)
                flat = self.flatten(chain_complex)
                elif_blocks.extend(flat[:-1])
                else_block = flat[-1]
            elif isinstance(c, PythonParser.Else_blockContext):
                else_block = self.visit(c)

        return IfStatement(expr, statements, elif_blocks, else_block or [])

    def visitStatement(self, ctx: PythonParser.StatementContext):
        for child in ctx.children:
            return self.visit(child)

    def visitSimple_stmts(self, ctx:PythonParser.Simple_stmtsContext):
        return self.visit(ctx.simple_stmt()[0])

    def visitBlock(self, ctx: PythonParser.BlockContext):
        statements = []
        for c in ctx.children:
            if not isinstance(c, PythonParser.StatementsContext):
                continue

            for stmt in c.statement():
                result = self.visit(stmt)
                statements.append(result)

        return statements

    def visitElif_stmt(self, ctx:PythonParser.Elif_stmtContext):
        expr = self.visit(ctx.children[1])
        block = self.visit(ctx.children[3])
        if ctx.elif_stmt():
            last = self.visit(ctx.children[-1])

            return ElifBlock(expr, block), last
        elif ctx.else_block():
            last = self.visit(ctx.children[-1])

            return ElifBlock(expr, block), last
        else:
            return ElifBlock(expr, block), None

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
                    child = ctx.children[0]
                    while not isinstance(child, PythonParser.SumContext):
                        child = child.children[0]

                    parts.append(self.visit(child))
                else:
                    parts.append(Constant(part, "int"))
        return parts

    def visitImport_stmt(self, ctx:PythonParser.Import_stmtContext):
        stmt: PythonParser.Import_sigContext = ctx.import_sig()
        params = stmt.import_params()
        param_list = []
        if params:
            for param in params.import_param():
                param_list.append(self.visit(param))

        ret_tpe = stmt.import_return_type()
        tpe = None
        if ret_tpe:
            tpe = ret_tpe.name().getText()

        self.statements.append(ImportStmt(stmt.name().getText(), param_list, tpe))

    def visitImport_param(self, ctx:PythonParser.Import_paramContext):
        print(ctx.children)
        name = ctx.children[0].getText()
        tpe = ctx.children[2].getText()
        return FuncArg(name, tpe)

    def flatten(self, tup):
        flat = []
        while type(tup[1]) == tuple:
            flat.append(tup[0])
            tup = tup[1]

        flat.append(tup[0])
        flat.append(tup[1])

        return flat