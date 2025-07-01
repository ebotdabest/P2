from plistlib import loads

from llvmlite import ir
from ast.ptypes import *
from llvmlite import binding as llvm


def evaluate_expression(builder, expr, scope, context=None):
    if isinstance(expr, Constant):
        return ir.Constant(scope[expr.tpe], usable_types[expr.tpe](expr.value))
    if isinstance(expr, VariableReference):
        if not isinstance(scope[expr.var], ir.Argument):
            loaded = builder.load(scope[expr.var])
        else:
            loaded = scope[expr.var]
        return loaded
    if isinstance(expr, BinaryOp):
        left = evaluate_expression(builder, expr.left, scope)
        right = evaluate_expression(builder, expr.right, scope)
        if isinstance(expr.left, Constant):
            tpe_l = scope[expr.left.tpe]
        elif isinstance(expr.left, VariableReference):
            tpe_l = scope[expr.left.var].type.pointee
        elif isinstance(expr.left, FuncCall):
            tpe_l = scope[expr.left.name].function_type.return_type
        else:
            tpe_l = None

        if isinstance(expr.right, Constant):
            tpe_r = scope[expr.right.tpe]
        elif isinstance(expr.right, VariableReference):
            tpe_r = scope[expr.right.var].type.pointee
        elif isinstance(expr.right, FuncCall):
            tpe_r = scope[expr.right.name].function_type.return_type
        else:
            tpe_r = None


        if tpe_l != scope[context["type"]]:
            if tpe_l == scope["int"]:
                left = builder.sitofp(left, scope[context["type"]])
            if tpe_l == scope["double"]:
                left = builder.fptrunc(left, scope[context["type"]])

        if tpe_r != scope[context["type"]]:
            if tpe_r == scope["int"]:
                right = builder.sitofp(right, scope[context["type"]])
            if tpe_r == scope["double"]:
                right = builder.fptrunc(right, scope[context["type"]])

        if tpe_r == scope["int"] and tpe_l == scope["int"]:
            if expr.op == "+": return builder.add(left, right)
            if expr.op == "*": return builder.mul(left, right)
            if expr.op == "-": return builder.sub(left, right)
            if expr.op == "/": return builder.sdiv(left, right)
        else:
            if expr.op == "+": return builder.fadd(left, right)
            if expr.op == "*": return builder.fmul(left, right)
            if expr.op == "-": return builder.fsub(left, right)
            if expr.op == "/": return builder.fdiv(left, right)

    if isinstance(expr, FuncCall):
        args = [evaluate_expression(builder, arg, scope) for arg in expr.args]
        return builder.call(scope[expr.name], args)

def handle_var_op(builder: ir.IRBuilder, stmt: VariableOp, scope):
    var = scope[stmt.var]
    value = evaluate_expression(builder, stmt.expression, scope)
    if stmt.op == "=":
        builder.store(value, var)

def handle_statements(builder: ir.IRBuilder, statements, scope, func = None):
    for stmt in statements:
        if isinstance(stmt, FuncCall):
            builder.call(scope[stmt.name], [])
        if isinstance(stmt, ReturnStatement):
            builder.ret(evaluate_expression(builder, stmt.expr, scope, {"type": func.function_type.return_type}))
        if isinstance(stmt, VariableCreation):
            ptr = builder.alloca(scope[stmt.tpe], name=stmt.name)
            value = evaluate_expression(builder, stmt.value, scope, {"type": stmt.tpe})

            if value.type != scope[stmt.tpe]:
                if value.type == scope["float"]:
                    value = builder.fptosi(value, scope[stmt.tpe])
                elif value.type == scope["int"]:
                    value = builder.sitofp(value, scope[stmt.tpe])
            builder.store(value, ptr)
            scope[stmt.name] = ptr
        if isinstance(stmt, VariableOp): handle_var_op(builder, stmt, scope)
        if isinstance(stmt, IfStatement):
            if_main = func.append_basic_block()
            if_main_builder = ir.IRBuilder(if_main)
            continue_entry = func.append_basic_block()
            continue_entry_builder = ir.IRBuilder(continue_entry)

            handle_statements(if_main_builder, stmt.block, scope, func)
            if not if_main.is_terminated:
                if_main_builder.branch(continue_entry)

            parts, part_builder = [], []
            for part in stmt.expr:
                if isinstance(part, ConditionToken):
                    if part.token == "and" or part.token == "or":
                        parts.append(part_builder)
                        parts.append(part)
                        part_builder = []
                        continue
                part_builder.append(part)
            parts.append(part_builder)
            next_label = continue_entry

            for i, cond in enumerate(parts):
                if i == 0:
                    left = evaluate_expression(builder, cond[0], scope)
                    token = cond[1].token
                    right = evaluate_expression(builder, cond[2], scope)
                    if len(parts) > 1:
                        next_label = func.append_basic_block()
                        cond_token = parts[i + 1].token
                        if cond_token == "and":
                            condition = builder.icmp_signed(token, left, right)
                            builder.cbranch(condition, if_main, continue_entry)
                            continue
                    condition = builder.icmp_signed(token, left, right)
                    builder.cbranch(condition, if_main, next_label)
                if i % 2 == 0 and i != 0:
                    if next_label == continue_entry: continue

                    next_builder = ir.IRBuilder(next_label)

                    left = evaluate_expression(next_builder, cond[0], scope)
                    token = cond[1].token
                    right = evaluate_expression(next_builder, cond[2], scope)
                    if i != len(parts) - 1:
                        next_label = func.append_basic_block()
                    else:
                        next_label = continue_entry
                    condition = next_builder.icmp_signed(token, left, right)
                    next_builder.cbranch(condition, if_main, next_label)



            if stmt.else_block:
                handle_statements(continue_entry_builder, stmt.else_block, scope, func)
                actual_continue = func.append_basic_block()
                if not continue_entry.is_terminated:
                    continue_entry_builder.branch(actual_continue)
                actual_continue_builder = ir.IRBuilder(actual_continue)

                builder = actual_continue_builder
            else:
                builder = continue_entry_builder

    return builder
def function_definition(module, expr: FunctionDefinition, global_scope):
    args = []
    for arg in expr.args:
        if isinstance(arg, FuncArg):
            args.append(global_scope[arg.tpe])

    head = ir.FunctionType(global_scope[expr.return_type] if expr.return_type else ir.VoidType(), args)
    func = ir.Function(module, head, expr.func_name)
    entry = func.append_basic_block("entry")
    builder = ir.IRBuilder(entry)
    scope = {} | global_scope
    for i, arg in enumerate(expr.args):
        scope[arg.name] = func.args[i]

    global_scope[expr.func_name] = func
    bblock = handle_statements(builder, expr.statements, scope, func)

    if not bblock.block.is_terminated:
        bblock.unreachable()


def compile_ast(file_ast):
    module = ir.Module(name="P2-main")
    types = {
        "int": ir.IntType(32),
        "float": ir.FloatType(),
        "double": ir.DoubleType(),
        "bool": ir.IntType(8)
    }

    global_scope = {} | types
    for expr in file_ast:
        if isinstance(expr, FunctionDefinition):
            function_definition(module, expr, global_scope)

    return module

def run_module(module):
    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    llvm_ir = str(module)
    mod = llvm.parse_assembly(llvm_ir)
    mod.verify()

    target = llvm.Target.from_default_triple()
    target_machine = target.create_target_machine()
    engine = llvm.create_mcjit_compiler(mod, target_machine)

    engine.finalize_object()

    # obj_code = target_machine.emit_object(mod)
    #
    # with open("output.o", "wb") as f:
    #     f.write(obj_code)

    func_ptr = engine.get_function_address("main")

    from ctypes import CFUNCTYPE, c_int, c_bool
    func = CFUNCTYPE(c_int, c_int)(func_ptr)
    return func, engine
