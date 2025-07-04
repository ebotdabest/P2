from llvmlite import ir
from ast.ptypes import *
from llvmlite import binding as llvm


def evaluate_expression(builder: ir.IRBuilder, expr, scope, context=None):
    if isinstance(expr, Constant):
        if expr.tpe == "str":
            chars = usable_types[expr.tpe](expr.value)
            args = [ir.Constant(ir.IntType(32), len(chars))]
            for char in chars:
                args.append(ir.Constant(ir.IntType(8), char))
            return builder.call(scope["__p2_make_string"], args)
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

            tpe_l = scope[expr.left.var].allocated_type
        elif isinstance(expr.left, FuncCall):
            tpe_l = scope[expr.left.name].function_type.return_type
        else:
            tpe_l = None

        if isinstance(expr.right, Constant):
            tpe_r = scope[expr.right.tpe]
        elif isinstance(expr.right, VariableReference):
            tpe_r = scope[expr.right.var].allocated_type
        elif isinstance(expr.right, FuncCall):
            tpe_r = scope[expr.right.name].function_type.return_type
        else:
            tpe_r = None

        if context:
            if tpe_l != context["type"]:
                if tpe_l == scope["int"]:
                    left = builder.sitofp(left, context["type"])
                if tpe_l == scope["double"]:
                    left = builder.fptrunc(left, context["type"])

            if tpe_r != context["type"]:
                if tpe_r == scope["int"]:
                    right = builder.sitofp(right, context["type"])
                if tpe_r == scope["double"]:
                    right = builder.fptrunc(right, context["type"])

        if tpe_r == scope["int"] and tpe_l == scope["int"]:
            if expr.op == "+": return builder.add(left, right)
            if expr.op == "*": return builder.mul(left, right)
            if expr.op == "-": return builder.sub(left, right)
            if expr.op == "/": return builder.sdiv(left, right)
            if expr.op == "//": return builder.call(scope["__p2_floor_div"], [left, right])
            if expr.op == "%": return builder.call(scope["__p2_mod_div"], [left, right])
        else:
            if expr.op == "+": return builder.fadd(left, right)
            if expr.op == "*": return builder.fmul(left, right)
            if expr.op == "-": return builder.fsub(left, right)
            if expr.op == "/": return builder.fdiv(left, right)
            if expr.op == "//": return builder.call(scope["__p2_floor_div"], [left, right])
            if expr.op == "%": return builder.call(scope["__p2_mod_div"], [left, right])

    if isinstance(expr, FuncCall):
        args = [evaluate_expression(builder, arg, scope) for arg in expr.args]
        return builder.call(scope[expr.name], args)

def handle_var_op(builder: ir.IRBuilder, stmt: VariableOp, scope):
    var = scope[stmt.var]
    value = evaluate_expression(builder, stmt.expression, scope)
    if stmt.op == "=":
        builder.store(value, var)

def flatten_condition(expr):
    if isinstance(expr, BinaryOp):
        return flatten_condition(expr.left) + [ConditionToken(expr.op)] + flatten_condition(expr.right)
    elif isinstance(expr, UnaryOp):
        return [ConditionToken(expr.op)] + flatten_condition(expr.op)
    else:
        return [expr]

def expr_prettify(expression):
    if not isinstance(expression, list):
        expression = flatten_condition(expression)

    parts = []
    i = 0
    while i < len(expression):
        part = expression[i]

        if isinstance(part, ConditionToken) and part.token in ("and", "or", "(", ")"):
            parts.append(part)
            i += 1
            continue

        sub = []
        while i < len(expression):
            if isinstance(expression[i], ConditionToken) and expression[i].token in ("and", "or", "(", ")"):
                break
            sub.append(expression[i])
            i += 1

        if len(sub) not in (1, 2, 3):
            raise ValueError(f"Malformed condition group: {sub}")
        parts.append(sub)

    return parts


def get_condition_signed(cond, builder: ir.IRBuilder, scope):
    if len(cond) == 1:
        value = evaluate_expression(builder, cond[0], scope)

        one = ir.Constant(ir.IntType(8), 1)

        if isinstance(value.type, ir.IntType) and value.type.width == 8:
            return builder.icmp_signed("==", value, one)

        return builder.icmp_signed("!=", value, ir.Constant(value.type, 0))

    if len(cond) == 3 and isinstance(cond[1], ConditionToken):
        left = evaluate_expression(builder, cond[0], scope)
        right = evaluate_expression(builder, cond[2], scope)

        return builder.icmp_signed(cond[1].token, left, right)

def handle_conditional_expr(builder: ir.IRBuilder, scope, expr, success, fail):
    parts = expr_prettify(expr)
    elements = []
    for i, cond in enumerate(parts):
        if not cond: continue
        if isinstance(cond, ConditionToken):
            elements.append(cond)
            continue
        elements.append(get_condition_signed(cond, builder, scope))

    i, final = 1, elements[0]
    while i < len(elements):
        sep = elements[i]
        right = elements[i + 1]

        if sep.token == "and":
            final = builder.and_(final, right)
        elif sep.token == "or":
            final = builder.or_(final, right)

        i += 2

    builder.cbranch(final, success, fail)

def handle_else_if(elseif: ElifBlock, assigned_label, next_label, scope, func):
    builder = ir.IRBuilder(assigned_label)
    block = func.append_basic_block()
    logic_builder = ir.IRBuilder(block)
    handle_statements(logic_builder, elseif.block, scope, func)
    handle_conditional_expr(builder, scope, elseif.expr, block, next_label)

def handle_statements(builder: ir.IRBuilder, statements, scope, func):
    for stmt in statements:
        if isinstance(stmt, FuncCall):
            args = []
            for arg in stmt.args:
                args.append(evaluate_expression(builder, arg, scope))

            builder.call(scope[stmt.name], args)
        if isinstance(stmt, ReturnStatement):
            print(stmt)
            builder.ret(evaluate_expression(builder, stmt.expr, scope, {"type":
                                                                            func.function_type.return_type}))
        if isinstance(stmt, VariableCreation):
            if stmt.tpe == "str":
                tpe = "strt"
            else:
                tpe = stmt.tpe
            ptr = builder.alloca(scope[tpe], name=stmt.name)
            value = evaluate_expression(builder, stmt.value, scope, {"type": scope[stmt.tpe]})

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


            labels = [func.append_basic_block() for _ in stmt.elifs]
            labels.append(continue_entry)

            next_label = continue_entry
            if len(labels) > 0:
                next_label = labels[0]

            handle_conditional_expr(builder, scope, stmt.expr, if_main, next_label)

            if stmt.else_block:
                handle_statements(continue_entry_builder, stmt.else_block, scope, func)
                actual_continue = func.append_basic_block()
                if not continue_entry.is_terminated:
                    continue_entry_builder.branch(actual_continue)
                actual_continue_builder = ir.IRBuilder(actual_continue)

                builder = actual_continue_builder
            else:
                builder = continue_entry_builder

            for i, ei in enumerate(stmt.elifs):
                assigned_label = labels[i]
                next_if_label = labels[i + 1]
                handle_else_if(ei,assigned_label, next_if_label, scope, func)

    return builder
def function_definition(module, expr: FunctionDefinition, global_scope):
    args = []
    for arg in expr.args:
        if isinstance(arg, FuncArg):
            args.append(global_scope[arg.tpe])

    if expr.func_name in global_scope:
        func = global_scope[expr.func_name]
    else:
        head = ir.FunctionType(global_scope[expr.return_type] if expr.return_type else ir.VoidType(), args)
        func = ir.Function(module, head, expr.func_name)
        func.linkage = 'internal'

    entry = func.append_basic_block("entry")
    builder = ir.IRBuilder(entry)
    scope = {} | global_scope
    for i, arg in enumerate(expr.args):
        ptr = builder.alloca(scope[arg.tpe])
        builder.store(func.args[i], ptr)
        scope[arg.name] = ptr


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
        "bool": ir.IntType(8),
        "str": ir.PointerType(),
        "strt": ir.IntType(8).as_pointer()
    }

    head = ir.FunctionType(ir.IntType(32), [ir.IntType(32), ir.IntType(32)])
    floor_div = ir.Function(module, head, "p2_floor")
    mod_div = ir.Function(module, head, "p2_mod")
    make_str = ir.Function(module, ir.FunctionType(ir.PointerType(), [ir.IntType(32)], True),
                           "create_string_array")

    global_scope = {} | types
    global_scope["__p2_floor_div"] = floor_div
    global_scope["__p2_mod_div"] = mod_div
    global_scope["__p2_make_string"] = make_str
    for expr in file_ast:
        if isinstance(expr, FunctionDefinition):
            function_definition(module, expr, global_scope)
        if isinstance(expr, ImportStmt):
            args = [global_scope[arg.tpe] for arg in expr.args if isinstance(arg, FuncArg)]
            va_args = isinstance(expr.args[-1], VAArgs)

            tpe = ir.FunctionType(global_scope[expr.return_type] if expr.return_type else ir.VoidType(), args, va_args)
            func = ir.Function(module, tpe, name=expr.func_name)
            global_scope[expr.func_name] = func
        if isinstance(expr, GlobalStmt):
            for symbol in expr.names:
                if symbol in global_scope.keys():
                    global_scope[symbol].linkage = ''


    return module

from ctypes import CFUNCTYPE, c_int, c_bool, cast, c_void_p


P2HELPERS = """
define i32 @p2_floor(i32 %a, i32 %b) {
entry:
  %div = sdiv i32 %a, %b
  %rem = srem i32 %a, %b
  %cond = icmp ne i32 %rem, 0

  %xor_ab = xor i32 %a, %b
  %sign_mismatch = icmp slt i32 %xor_ab, 0

  %need_floor = and i1 %cond, %sign_mismatch

  %div_minus_1 = sub i32 %div, 1
  %floor_div = select i1 %need_floor, i32 %div_minus_1, i32 %div

  ret i32 %floor_div
}

define i32 @p2_mod(i32 %a, i32 %b) {
entry:
  %floor_div = call i32 @p2_floor(i32 %a, i32 %b)
  %mul = mul i32 %b, %floor_div
  %mod = sub i32 %a, %mul
  ret i32 %mod
}
"""

def get_engine(module: ir.Module):
    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()
    target = llvm.Target.from_default_triple()
    target_machine = target.create_target_machine()

    helper = llvm.parse_assembly(P2HELPERS)
    helper.verify()

    module.triple = llvm.get_default_triple()
    module.data_layout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"

    llvm_ir = str(module)

    with open("output.ll", "w") as f:
        f.write(llvm_ir)

    mod = llvm.parse_assembly(llvm_ir)
    mod.verify()
    mod.link_in(helper)

    engine = llvm.create_mcjit_compiler(mod, target_machine)

    engine.finalize_object()

    return engine, target_machine, mod

def run_module(module):
    engine, target_machine, mod = get_engine(module)
    func_ptr = engine.get_function_address("main")

    func = CFUNCTYPE(c_int)(func_ptr)
    return func, engine

def compile_module(module):
    engine, target_machine, mod = get_engine(module)
    obj_code = target_machine.emit_object(mod)

    with open("output.o", "wb") as f:
        f.write(obj_code)