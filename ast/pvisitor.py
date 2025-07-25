import antlr4

from ast import PythonParser
from ast.gen.PythonParserVisitor import PythonParserVisitor
from ast.ptypes import *
from errors import NoTypeError
from typing import List
from ast.expression_parser import parse_expression
from antlr4.tree.Tree import TerminalNodeImpl

class P2Visitor(PythonParserVisitor):
    def __init__(self):
        super().__init__()
        self.statements = []
        self.scope = {}

    def read_result(self):
        return self.statements

    def send_to_top(self, stmt):
        self.statements.append(stmt)

    def visitFactor(self, ctx:PythonParser.FactorContext):
        if len(ctx.children) == 1:
            return self.visitChildren(ctx)

        value = self.visit(ctx.children[1])
        value.value = f"{ctx.children[0].getText()}{value.value}"
        return value


    def visitFunction_def_raw(self, ctx):
        func_name = ctx.name().getText()
        return_type = self._extract_return_type(ctx)

        args = self._extract_parameters(ctx)
        body = self._parse_block(ctx.block())
        func = FunctionDefinition(func_name, args, body, return_type)
        self.send_to_top(func)

    def _extract_return_type(self, ctx):
        # Find "-> type"
        for i, child in enumerate(ctx.children):
            if child.getText() == "->":
                return ctx.getChild(i + 1).getText()
        return None

    def _extract_parameters(self, ctx) -> List:
        args = []
        param_ctx = ctx.params()
        if not param_ctx:
            return args

        for param in param_ctx.parameters().param_no_default():
            param = param.param()
            if not param.annotation():
                raise NoTypeError(param.name().getText())
            name = param.name().getText()
            tpe = self.visit(param.annotation())
            args.append(FuncArg(name, tpe))

        for param in param_ctx.parameters().param_with_default():
            param = param.param()
            if not param.annotation():
                raise NoTypeError(param.name().getText())
            name = param.name().getText()
            tpe = param.annotation().getText()
            default = self.visit(param_ctx.parameters().default_assignment())
            args.append(FuncDefaultArg(name, tpe, default))

        return args

    def _parse_block(self, block_ctx):
        statements = []

        if not block_ctx or not block_ctx.statements():
            return statements

        for stmt_ctx in block_ctx.statements().statement():
            result = self.visit(stmt_ctx)

            if result is not None:
                statements.append(result)

        return statements

    def visitAssignment(self, ctx):
        if ctx.name():
            var_name = ctx.name().getText()

            tpe = self.visit(ctx.expression())

            value = None
            if ctx.annotated_rhs():
                value = self.visit(ctx.annotated_rhs())

            if isinstance(value, Constant):
                if value.tpe.startswith("list-"):
                    value.tpe = "list-" + tpe.slices[0]

            stmt = VariableCreation(var_name, tpe, value)
            self.scope[var_name] = stmt

            return stmt

        if ctx.augassign():
            target = self.visit(ctx.single_target())
            op = ctx.augassign().getText()
            value = self.visit(ctx.star_expressions())
            return VariableOp(target, value, op)

        if ctx.star_targets():
            target = self.visit(ctx.star_targets()[0])
            value = self.visit(ctx.star_expressions())
            return VariableOp(target, value, "=")

        raise Exception("Unhandled assignment case")

    def visitTarget_with_star_atom(self, ctx:PythonParser.Target_with_star_atomContext):
        text = ctx.getText()
        if "[" in text:
            var_name = ctx.children[0].getText()
            slices = self._parse_literal_or_variable(ctx.children[2].getText())

            return SliceOp(var_name, [slices])

        return self._parse_literal_or_variable(ctx.getText())

    def visitSingle_target(self, ctx:PythonParser.Single_targetContext):
        return self._parse_literal_or_variable(ctx.getText())

    def visitSlices(self, ctx:PythonParser.SlicesContext):
        parent: PythonParser.PrimaryContext = ctx.parentCtx
        var = parent.primary().atom().name().getText()
        slices = [self._parse_literal_or_variable(s.getText()) for s in ctx.slice_()]

        return SliceOp(var, slices)

    def visitAnnotated_rhs(self, ctx):
        if ctx.yield_expr():
            return self.visit(ctx.yield_expr())
        return self.visit(ctx.star_expressions())


    def visitBlock(self, ctx):
        statements = []
        for stmt_ctx in ctx.statements().statement():
            stmt = self.visit(stmt_ctx)
            if stmt:
                statements.append(stmt)
        return statements


    def visitIf_stmt(self, ctx):
        condition = self.visit(ctx.named_expression())
        then_block = self.visit(ctx.block())

        elif_blocks = []
        else_block = None

        if ctx.elif_stmt():
            elif_blocks, else_block = self.visit(ctx.elif_stmt())

        if ctx.else_block():
            else_block = self.visit(ctx.else_block())

        return IfStatement(condition, then_block, elif_blocks, else_block)

    def visitElif_stmt(self, ctx):
        condition = self.visit(ctx.named_expression())
        block = self.visit(ctx.block())
        current_block = ElifBlock(condition, block)

        elif_blocks = [current_block]
        else_block = None

        if ctx.elif_stmt():
            next_elifs, else_block = self.visit(ctx.elif_stmt())
            elif_blocks.extend(next_elifs)
        elif ctx.else_block():
            else_block = self.visit(ctx.else_block())

        return elif_blocks, else_block

    def visitElse_block(self, ctx):
        return self.visit(ctx.block())

    def _parse_literal_or_variable(self, text):
        if text in ("True", "False"):
            return Constant(text, "bool")

        if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
            return Constant(text[1:-1], "str")

        if "." in text and self._is_float(text):
            return Constant(text, "float")

        if text.isdigit() or (text.startswith('-') and text[1:].isdigit()):
            return Constant(text, "int")


        return VariableReference(text)

    def _is_float(self, s):
        try:
            float(s)
            return True
        except ValueError:
            return False

    def visitPrimary(self, ctx):
        if ctx.slices():
            return self.visit(ctx.slices())

        current = ctx
        call_chain = []

        while hasattr(current, 'children'):
            children = current.children

            if len(children) > 1 and children[1].getText() == "(":
                func_ctx = children[0]

                if hasattr(func_ctx, 'children') and len(func_ctx.children) >= 3 and func_ctx.children[
                    1].getText() == '.':
                    method_name = func_ctx.children[2].getText()
                    root_ctx = func_ctx.children[0]
                else:
                    method_name = func_ctx.getText()
                    root_ctx = None

                if current.arguments():
                    args = [self.visit(arg) for arg in current.arguments().args().expression()]
                else:
                    args = []

                call_chain.insert(0, FuncCall(method_name, args))

                if root_ctx:
                    current = root_ctx
                else:
                    break
            else:
                break

        atom = current.atom()
        if atom:
            if atom.list_():
                root = self.visit(atom.list_())
            else:
                root = self._parse_literal_or_variable(atom.getText())
        else:
            root = self.visitChildren(current)

        if not call_chain:
            return root
        elif len(call_chain) == 1 and isinstance(root, str) and root is None:
            return call_chain[0]
        else:
            if not root:
                return call_chain[0]
            return CallChain(root, call_chain)

    def visitList(self, ctx:PythonParser.ListContext):
        if len(ctx.children) == 2:
            return Constant([], "list-")

        return self.visit(ctx.getChild(1))

    def visitSum(self, ctx):
        return self._parse_bin_chain(ctx)

    def visitStatement(self, ctx):
        for child in ctx.children:
            result = self.visit(child)
            if result is not None:
                return result
        return None

    def visitSimple_stmts(self, ctx):
        for stmt in ctx.simple_stmt():
            result = self.visit(stmt)
            if result is not None:
                return result
        return None

    def visitSimple_stmt(self, ctx):
        for child in ctx.children:
            result = self.visit(child)
            if result is not None:
                return result

        if str(ctx.children[0]) == "break":
            return BreakStmt()
        elif str(ctx.children[0]) == "continue":
            return ContinueStmt()
        return None

    def visitTerm(self, ctx):
        return self._parse_bin_chain(ctx)

    def _parse_bin_chain(self, ctx):
        if len(ctx.children) == 1:
            return self.visitChildren(ctx)

        left = self.visit(ctx.children[0])
        i = 1
        while i < len(ctx.children) - 1:
            op = ctx.children[i].getText()
            right = self.visit(ctx.children[i + 1])
            left = BinaryOp(left, op, right)
            i += 2
        return left

    def visitNamed_expression(self, ctx):
        text = ctx.getText()
        expr = parse_expression(text)

        return expr

    def visitExpression(self, ctx):
        if ctx.getChildCount() == 1:
            return self.visitChildren(ctx)

        cond = self.visit(ctx.getChild(1))
        true_expr = self.visit(ctx.getChild(0))
        false_expr = self.visit(ctx.getChild(4))
        return TernaryOp(cond, true_expr, false_expr)

    def visitDisjunction(self, ctx):
        if ctx.getChildCount() == 1:
            return self.visitChildren(ctx)

        left = self.visit(ctx.getChild(0))
        i = 1
        while i < ctx.getChildCount():
            op = ctx.getChild(i).getText()  # 'or'
            right = self.visit(ctx.getChild(i + 1))
            left = BinaryOp(left, op, right)
            i += 2
        return left

    def visitConjunction(self, ctx):
        if ctx.getChildCount() == 1:
            return self.visitChildren(ctx)

        left = self.visit(ctx.getChild(0))
        i = 1
        while i < ctx.getChildCount():
            op = ctx.getChild(i).getText()  # 'and'
            right = self.visit(ctx.getChild(i + 1))
            left = BinaryOp(left, op, right)
            i += 2
        return left

    def visitInversion(self, ctx):
        if ctx.getChildCount() == 1:
            return self.visitChildren(ctx)

        operand = self.visit(ctx.getChild(1))
        return UnaryOp("not", operand)

    def visitComparison(self, ctx):
        if ctx.getChildCount() == 1:
            return self.visitChildren(ctx)

        left = self.visit(ctx.getChild(0))
        i = 1
        while i < ctx.getChildCount() - 1:
            op = ctx.getChild(i).getText()
            right = self.visit(ctx.getChild(i + 1))
            left = BinaryOp(left, op, right)
            i += 2
        return left

    def visitImport_stmt(self, ctx):
        sig = ctx.import_sig()
        import_name = sig.name().getText()

        header = sig.import_params_header()
        param_list = []
        if header:
            if header.import_params():
                for param in header.import_params().import_param():
                    param_list.append(self.visit(param))

            if header.import_va_args():
                param_list.append(VAArgs())

        ret_type = None
        if sig.import_return_type():
            ret_type = sig.import_return_type().name().getText()

        self.send_to_top(ImportStmt(import_name, param_list, ret_type))

    def visitImport_param(self, ctx):
        name = ctx.name(0).getText()
        tpe = ctx.name(1).getText()
        return FuncArg(name, tpe)

    def visitReturn_stmt(self, ctx):
        if ctx.star_expressions():
            value = self.visitChildren(ctx.star_expressions().star_expression()[0])
        else:
            value = None
        return ReturnStatement(value)

    def visitStar_expressions(self, ctx:PythonParser.Star_expressionsContext):
        return self.visitChildren(ctx)

    def visitStar_expression(self, ctx:PythonParser.Star_expressionContext):
        return self.visitChildren(ctx)

    def visitStar_named_expressions(self, ctx:PythonParser.Star_named_expressionsContext):
        value = []
        for child in ctx.children:
            r = self.visit(child)
            if r:
                value.append(r.expr)

        return Constant(value, "list")


    def visitStar_named_expression(self, ctx:PythonParser.Star_named_expressionContext):
        return self.visit(ctx.named_expression())


    def visitGlobal_stmt(self, ctx):
        symbols = [n.getText() for n in ctx.name()]
        self.send_to_top(GlobalStmt(symbols))

    def flatten(self, tup):
        flat = []
        while tup and isinstance(tup[0], ElifBlock):
            flat.append(tup[0])
            tup = tup[1]
        return flat, tup[1] if tup else []

    def visitWhile_stmt(self, ctx:PythonParser.While_stmtContext):
        expr = self.visit(ctx.getChild(1))
        stmts = self.visit(ctx.children[-1])

        return WhileStmt(expr, stmts)
