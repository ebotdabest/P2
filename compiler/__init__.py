from llvmlite import ir
from ast.ptypes import *
from llvmlite import binding as llvm
from .gc import HeapObject, ObjectTracker
import os
import os.path as path
from .feature import request_feature, FUNCTIONS

class ScopeElement:
    def __init__(self, tpe, value):
        self.tpe = tpe
        self.value = value
target_machine: llvm.TargetMachine = None
def get_element_tpe(expr, scope):
    if isinstance(expr, FuncCall):
        return scope[expr.name].tpe
    if isinstance(expr, VariableReference):
        return scope[expr.var].tpe
    if isinstance(expr, Constant):
        return expr.tpe

    return "null"


def get_binding_type_size(ir_type):
    dummy_module = ir.Module(name="dummy")
    dummy_global = ir.GlobalVariable(dummy_module, ir_type, name="dummy_var")

    binding_module = llvm.parse_assembly(str(dummy_module))
    binding_module.verify()

    global_value = binding_module.get_global_variable("dummy_var")
    binding_type = global_value.type

    return target_machine.target_data.get_abi_size(binding_type)

def create_array(builder: ir.IRBuilder, tpe, size, values):
    arr = ir.ArrayType(tpe, size)
    ptr = builder.alloca(arr)
    indice = ir.Constant(ir.IntType(32), 0)
    for i in range(size):
        index_ptr = builder.gep(ptr, [indice, ir.Constant(ir.IntType(32), i)])
        index_ptr.type = ir.PointerType()
        val = values[i]

        builder.store(val, index_ptr)

    return ptr

def evaluate_expression(builder: ir.IRBuilder, expr, scope,func, tracker, context=None):
    if isinstance(expr, Constant):
        if expr.tpe == "str":
            chars = usable_types[expr.tpe](expr.value)
            args = [ir.Constant(ir.IntType(32), len(chars))]
            for char in chars:
                args.append(ir.Constant(ir.IntType(32), char))
            str_array = builder.call(scope["__p2_make_string"].value, args)
            tracker.add_object("str", str_array)
            return str_array
        elif expr.tpe.startswith("list") and context and context["type"] == "arr":
            size = len(expr.value)
            elements = []
            for value in expr.value:
                elements.append(evaluate_expression(builder, value[0], scope, func, tracker, context))

            return create_array(builder, context["arr_type"], size, elements)
        elif expr.tpe.startswith("list"):
            values = []
            for value in expr.value:
                val = evaluate_expression(builder, value[0], scope, func, tracker, context)
                values.append(val)

            split = expr.tpe.split("-")
            if len(split) == 1:
                if len(values) > 1:
                    ir_type = values[0].type
                else:
                    ir_type = scope["int"]
            else:
                ir_type = scope[split[1]]
            size = get_binding_type_size(ir_type)
            vector = builder.call(scope["__p2_make_vector"].value, [ir.Constant(ir.IntType(64), size)])

            for value in values:
                if str(value.type) != "ptr":
                    var = builder.alloca(value.type)
                    builder.store(value, var)
                    val = builder.bitcast(var, ir.PointerType())
                else:
                    val = value
                builder.call(scope["__t__list__append"].value, [vector, val])

            return vector

        if context:
            if "arg_tpe" in context.keys():
                arg_tpe = context["arg_tpe"]
                if scope[expr.tpe] != arg_tpe:
                    if "ptr" in str(arg_tpe):
                        mem = builder.alloca(scope[expr.tpe])
                        constant = ir.Constant(scope[expr.tpe], usable_types[expr.tpe](expr.value))
                        builder.store(constant, mem)
                        return mem

        return ir.Constant(scope[expr.tpe], usable_types[expr.tpe](expr.value))
    if isinstance(expr, VariableReference):
        if expr.var.startswith("_"):
            return scope[expr.var[1:]].value

        if isinstance(scope[expr.var].tpe, VariableReference):
            if scope[expr.var].tpe.var.startswith("ptr"):
                return scope[expr.var].value
        else:
            if scope[expr.var].tpe.startswith("ptr"):
                return scope[expr.var].value

        if isinstance(scope[expr.var].value, ir.CallInstr):
            return scope[expr.var].value

        return builder.load(scope[expr.var].value)
    if isinstance(expr, BinaryOp):
        left = evaluate_expression(builder, expr.left, scope, func, tracker)
        right = evaluate_expression(builder, expr.right, scope, func, tracker)
        if isinstance(expr.left, Constant):
            tpe_l = scope[expr.left.tpe]
        elif isinstance(expr.left, VariableReference):
            tpe_l = scope[expr.left.var].value.allocated_type
        elif isinstance(expr.left, FuncCall):
            tpe_l = scope[expr.left.name].value.function_type.return_type
        else:
            tpe_l = None

        if isinstance(expr.right, Constant):
            tpe_r = scope[expr.right.tpe]
        elif isinstance(expr.right, VariableReference):
            tpe_r = scope[expr.right.var].value.allocated_type
        elif isinstance(expr.right, FuncCall):
            tpe_r = scope[expr.right.name].value.function_type.return_type
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

        if tpe_r == scope["int"]:
            if expr.op == "+": return builder.add(left, right)
            if expr.op == "*": return builder.mul(left, right)
            if expr.op == "-": return builder.sub(left, right)
            if expr.op == "/": return builder.sdiv(left, right)
            if expr.op == "//": return builder.call(scope["__p2_floor_div"].value, [left, right])
            if expr.op == "%": return builder.call(scope["__p2_mod_div"].value, [left, right])
        elif tpe_r == scope["float"]:
            if expr.op == "+": return builder.fadd(left, right)
            if expr.op == "*": return builder.fmul(left, right)
            if expr.op == "-": return builder.fsub(left, right)
            if expr.op == "/": return builder.fdiv(left, right)
            if expr.op == "//": return builder.call(scope["__p2_floor_div"].value, [left, right])
            if expr.op == "%": return builder.call(scope["__p2_mod_div"].value, [left, right])

    if isinstance(expr, FuncCall):
        if expr.name == "len":
            obj = evaluate_expression(builder, expr.args[0], scope, func, tracker, context)
            tpe = scope[expr.args[0].var].tpe

            return builder.call(scope[f"__t__{tpe}____len__"].value, [obj])

        func_args = scope[expr.name].value.args
        arrs = expr.args
        args = [evaluate_expression(builder, arg, scope, func, tracker,
                                    {"arg_tpe": func_args[i]}) for
                i, arg in enumerate(arrs)]
        return builder.call(scope[expr.name].value, args)

    if isinstance(expr, ExprStatement):
        print("fuck me")
    if isinstance(expr, CallChain):
        root = expr.root
        FORMAT = "__t__{}__{}"

        root_call = None
        for i, call in enumerate(expr.calls):
            if isinstance(call, FuncCall):
                if i == 0:
                    args = call.args.copy()
                    args.insert(0,root)
                    tpe = get_element_tpe(root, scope)
                    root_call = FuncCall(FORMAT.format(tpe, call.name), args)
                    continue

                args = call.args.copy()
                args.insert(0, root_call)
                tpe = get_element_tpe(root_call, scope)
                root_call = FuncCall(FORMAT.format(tpe, call.name), args)

        fc = evaluate_expression(builder, root_call, scope, func, tracker, context)
        return fc

    if isinstance(expr, SliceOp):
        variable = scope[expr.var]
        if variable.tpe.startswith("arr"):
            index = evaluate_expression(builder, expr.slices[0], scope, func, tracker, context)

            ptr = builder.gep(variable.value, [ir.Constant(ir.IntType(32), 0),
                                            index])
            value = builder.load(ptr)
            return value
        else:
            index_value = evaluate_expression(builder, expr.slices[0], scope, func, tracker, context)
            result = builder.call(scope[f"__t__{variable.tpe}____index__"].value, [variable.value,
                                                           index_value])
            return result

    return expr

def handle_var_op_op(builder, var, value, op):
    if op == "=":
        builder.store(value, var)
    elif op == "+=":
        var_value = builder.load(var)
        final_value = builder.add(var_value, value)
        builder.store(final_value, var)
    elif op == "-=":
        var_value = builder.load(var)
        final_value = builder.srem(var_value, value)
        builder.store(final_value, var)
    elif op == "*=":
        var_value = builder.load(var)
        final_value = builder.mul(var_value, value)
        builder.store(final_value, var)
    elif op == "/=":
        var_value = builder.load(var)
        final_value = builder.sdiv(var_value, value)
        builder.store(final_value, var)

def handle_var_op(builder: ir.IRBuilder, stmt: VariableOp, scope, func, tracker):
    value = evaluate_expression(builder, stmt.expression, scope, func, tracker)
    if isinstance(stmt.var, SliceOp):
        var_name = stmt.var.var
        var = scope[var_name].value
        var_tpe = scope[var_name].tpe
        index = evaluate_expression(builder, stmt.var.slices[0], scope, func, tracker)
        if var_tpe.startswith("arr"):
            ptr = builder.gep(var, [ir.Constant(ir.IntType(32), 0), index])
            ptr.type = ir.PointerType()
            builder.store(value, ptr)
        else:
            builder.call(scope[f"__t__{var_tpe}____set_element__"].value, [var, value, index])
    else:
        var_name = stmt.var.var
        var = scope[var_name].value

        handle_var_op_op(builder, var, value, stmt.op)

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

    parts, builder = [], []
    for expr in expression:
        if isinstance(expr, ConditionToken) and expr.token in ["and", "or", "(", ")"]:
            parts.append(builder)
            parts.append(expr)
            builder = []
            continue

        builder.append(expr)

    parts.append(builder)
    return parts

def get_condition_signed(cond, builder: ir.IRBuilder, scope, func, tracker):
    if len(cond) == 1:
        value = evaluate_expression(builder, cond[0], scope, func, tracker)
        one = ir.Constant(ir.IntType(8), 1)

        if isinstance(value.type, ir.IntType) and value.type.width == 8:
            return builder.icmp_signed("==", value, one)
        return builder.icmp_signed("!=", value, ir.Constant(value.type, 0))

    if len(cond) == 3 and isinstance(cond[1], ConditionToken):
        left = evaluate_expression(builder, cond[0], scope, func, tracker)
        right = evaluate_expression(builder, cond[2], scope, func, tracker)

        if left.type == ir.PointerType() and right.type == ir.PointerType():
            if isinstance(cond[0], Constant):
                tpe_l = cond[0].tpe
            elif isinstance(cond[0], VariableReference):
                tpe_l = scope[cond[0].var].tpe

            if isinstance(cond[2], Constant):
                tpe_r = cond[2].tpe
            elif isinstance(cond[2], VariableReference):
                tpe_r = scope[cond[2].var].tpe

            if tpe_l == tpe_r:
                check = builder.call(scope[f"__t__{tpe_l}____eq__"].value, [left, right])
                return builder.icmp_signed(cond[1].token, check, ir.Constant(ir.IntType(8), 1))

        return builder.icmp_signed(cond[1].token, left, right)

def handle_conditional_expr(builder: ir.IRBuilder, scope, expr, success, fail, func, tracker: ObjectTracker):
    parts = expr_prettify(expr)
    elements = []

    for cond in parts:
        if not cond:
            continue
        if isinstance(cond, ConditionToken):
            elements.append(cond)
        else:
            elements.append(get_condition_signed(cond, builder, scope, func, tracker))

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


def handle_else_if(elseif: ElifBlock, scope, func, condition_label, continue_entry, extra = None):
    body = func.append_basic_block("else_if_body")
    condition_builder = ir.IRBuilder(condition_label)
    body_builder = ir.IRBuilder(body)
    next_condition = func.append_basic_block("else_if_condition")

    condition_tracker = ObjectTracker.create_tracker(condition_label)
    handle_conditional_expr(condition_builder, scope, elseif.expr.expr, body, next_condition, func, condition_tracker)
    condition_builder.position_before(condition_label.instructions[-1])

    # condition_tracker.free(scope, condition_builder, None)

    else_if_tracker = ObjectTracker.create_tracker(body)
    handle_statements(body_builder, elseif.block, scope, func, else_if_tracker, extra)

    if not body.is_terminated:
        body_builder.branch(continue_entry)

    return next_condition


def handle_else(else_content, scope, func, next_label, extra=None):
    else_block = func.append_basic_block("else_body")
    else_builder = ir.IRBuilder(else_block)
    else_tracker = ObjectTracker.create_tracker(else_block)
    handle_statements(else_builder, else_content, scope, func, else_tracker, extra)
    if not else_block.is_terminated:
        else_builder.branch(next_label)

    return else_block

def handle_statements(builder: ir.IRBuilder, statements, scope, func, tracker: ObjectTracker, extra=None):
    if extra is None:
        extra = {}
    ret = None
    for stmt in statements:
        if isinstance(stmt, FuncCall):
            func_args = scope[stmt.name].value.args
            arrs = stmt.args
            if len(func_args) < len(arrs):
                func_args = list(func_args).copy()
                diff = len(arrs) - len(func_args)
                for i in range(diff):
                    func_args.append(func_args[-1])

            args = [evaluate_expression(builder, arg, scope, func, tracker,
                                        {"arg_tpe": func_args[i]}) for
                    i, arg in enumerate(arrs)]
            builder.call(scope[stmt.name].value, args)

        elif isinstance(stmt, ReturnStatement):
            # tracker.free(scope, builder, None)
            ret = builder.ret(evaluate_expression(builder, stmt.expr, scope, func, tracker,{"type": func.function_type.return_type}))

        elif isinstance(stmt, VariableCreation):
            if isinstance(stmt.tpe, SliceOp) and stmt.tpe.var == "ptr":
                if isinstance(stmt.value, VariableReference):
                    scope[stmt.name] = ScopeElement(f"ptr;{stmt.tpe.slices[0]}", scope[stmt.value.var].value)
                if isinstance(stmt.value, FuncCall):
                    val = evaluate_expression(builder, stmt.value, scope, func, tracker)
                    tracker.add_object(stmt.tpe.slices[0], val)
                    scope[stmt.name] = ScopeElement(f"ptr;{stmt.tpe.slices[0]}", val)
                continue

            if stmt.tpe.var == "str":
                value = evaluate_expression(builder, stmt.value, scope, func, tracker,{"type": scope[stmt.tpe.var]})
                tracker.add_object("str", value)
                scope[stmt.name] = ScopeElement("str", value)
            elif stmt.tpe.var == "ptr":
                value = evaluate_expression(builder, stmt.value, scope, func, tracker, {"type": scope[stmt.tpe.var]})
                scope[stmt.name] = ScopeElement("ptr", value)
            elif stmt.tpe.var == "list":
                value = evaluate_expression(builder, stmt.value, scope, func, tracker, {"type": scope[stmt.tpe.var]})
                scope[stmt.name] = ScopeElement("list", value)
            elif stmt.tpe.var == "arr":

                value = evaluate_expression(builder, stmt.value, scope, func, tracker, {"type": "arr",
                                                                                "arr_type": scope[stmt.tpe.slices[0].var]})
                scope[stmt.name] = ScopeElement(f"arr-{stmt.tpe.slices[0]}", value)
            else:
                tpe = stmt.tpe.var
                ptr = builder.alloca(scope[tpe], name=stmt.name)
                value = evaluate_expression(builder, stmt.value, scope, func, tracker,{"type": scope[stmt.tpe.var]})

                if value.type != scope[stmt.tpe.var]:
                    if value.type == scope["float"]:
                        value = builder.fptosi(value, scope[stmt.tpe.var])
                    elif value.type == scope["int"]:
                        value = builder.sitofp(value, scope[stmt.tpe.var])

                if value.type.is_pointer:
                    value = builder.load(value, typ=scope[tpe])

                builder.store(value, ptr)
                scope[stmt.name] = ScopeElement(tpe, ptr)

        elif isinstance(stmt, VariableOp):
            handle_var_op(builder, stmt, scope, func, tracker)

        elif isinstance(stmt, IfStatement):
            if_body = func.append_basic_block("if_body")
            if_body_builder = ir.IRBuilder(if_body)
            continue_entry = func.append_basic_block("if_exit")

            body_tracker = ObjectTracker.create_tracker(if_body)
            handle_statements(if_body_builder, stmt.block, scope, func, body_tracker, extra)

            if stmt.elifs:
                condition_label = func.append_basic_block("else_if_condition")
                handle_conditional_expr(builder, scope, stmt.expr.expr, if_body, condition_label, func, tracker)
                for i, ei in enumerate(stmt.elifs):
                    if i + 1 == len(stmt.elifs):
                        if stmt.else_block:
                            else_block = handle_else(stmt.else_block, scope, func, continue_entry)

                            condition_builder = ir.IRBuilder(condition_label)
                            final_else_if = func.append_basic_block("else_if_body")
                            final_else_if_builder = ir.IRBuilder(final_else_if)

                            ct = ObjectTracker.create_tracker(condition_label)
                            eit = ObjectTracker.create_tracker(final_else_if)
                            handle_statements(final_else_if_builder, ei.block, scope, func, eit, extra)

                            handle_conditional_expr(condition_builder, scope, ei.expr.expr, final_else_if, else_block, func, ct)
                            if not final_else_if.is_terminated:
                                final_else_if_builder.branch(continue_entry)
                            break
                        else:
                            condition_label = handle_else_if(ei, scope, func, condition_label, continue_entry)
                    else:
                        condition_label = handle_else_if(ei, scope, func, condition_label, continue_entry)



            elif stmt.else_block:
                else_block = handle_else(stmt.else_block, scope, func, continue_entry)

                handle_conditional_expr(builder, scope, stmt.expr.expr, if_body, else_block, func, tracker)
            else:
                handle_conditional_expr(builder, scope, stmt.expr.expr, if_body, continue_entry, func, tracker)

            if not if_body.is_terminated:
                if_body_builder.branch(continue_entry)

            builder = ir.IRBuilder(continue_entry)
        elif isinstance(stmt, WhileStmt):
            body = func.append_basic_block()
            body_builder = ir.IRBuilder(body)

            condition_label = func.append_basic_block()
            condition_builder = ir.IRBuilder(condition_label)
            condition_tracker = ObjectTracker.create_tracker(condition_label)
            builder.branch(condition_label)

            body_tracker = ObjectTracker.create_tracker(body)

            next_label = func.append_basic_block()
            next_builder = ir.IRBuilder(next_label)

            handle_conditional_expr(condition_builder, scope, stmt.expr.expr, body, next_label, func, condition_tracker)

            helpers = {
                "cond": condition_label,
                "end": next_label
            }
            b2 = handle_statements(body_builder, stmt.stmts, scope, func, body_tracker, extra=helpers)
            b2.branch(condition_label)
            builder = next_builder
        elif isinstance(stmt, BreakStmt):
            if not extra:
                return

            builder.branch(extra["end"])
        elif isinstance(stmt, ContinueStmt):
            if not extra:
                return

            builder.branch(extra["cond"])
        elif isinstance(stmt, CallChain):
            root = stmt.root
            FORMAT = "__t__{}__{}"

            root_call = None
            for i, call in enumerate(stmt.calls):
                if isinstance(call, FuncCall):
                    if i == 0:
                        args = call.args.copy()
                        args.insert(0,root)
                        tpe = get_element_tpe(root, scope)
                        root_call = FuncCall(FORMAT.format(tpe, call.name), args)
                        continue

                    args = call.args.copy()
                    args.insert(0, root_call)
                    tpe = get_element_tpe(root_call, scope)
                    root_call = FuncCall(FORMAT.format(tpe, call.name), args)

            evaluate_expression(builder, root_call, scope, func, tracker)


    # if not builder.block.is_terminated:
    #     tracker.free(scope, builder, ret)

    return builder

def function_definition(module, expr: FunctionDefinition, global_scope):
    args = []
    for arg in expr.args:
        if isinstance(arg, FuncArg):
            if isinstance(arg.tpe, SliceOp):
                if arg.tpe.var == "ptr":
                    ptr_tpe = arg.tpe.slices[0]
                    args.append(global_scope[ptr_tpe].as_pointer())
                    continue
            args.append(global_scope[arg.tpe.var])

    if expr.func_name in global_scope:
        func = global_scope[expr.func_name].value
    else:
        head = ir.FunctionType(global_scope[expr.return_type] if expr.return_type else ir.VoidType(), args)
        func = ir.Function(module, head, expr.func_name)
        if expr.func_name != "main":
            func.linkage = 'internal'

    tracker = ObjectTracker.create_tracker(func)
    entry = func.append_basic_block("entry")
    builder = ir.IRBuilder(entry)

    scope = GlobalScope(module)
    scope.values = global_scope.values.copy()

    for i, arg in enumerate(expr.args):
        if arg.tpe.var == "ptr":
            scope[arg.name] = ScopeElement(arg.tpe, func.args[i])
            continue
        ptr = builder.alloca(scope[arg.tpe.var])
        builder.store(func.args[i], ptr)
        scope[arg.name] = ScopeElement(arg.tpe, ptr)


    global_scope[expr.func_name] = ScopeElement(expr.return_type, func)
    bblock = handle_statements(builder, expr.statements, scope, func, tracker)

    if bblock.function.function_type.return_type == ir.VoidType():
        bblock.ret_void()

    if not bblock.block.is_terminated:
        bblock.unreachable()


def extern_declare(mod, func_name, rt, args, va=False):
    head = ir.FunctionType(rt, args, va)
    return ir.Function(mod, head, func_name)

class GlobalScope(dict):
    def __init__(self, module):
        super().__init__()
        self.values = {}
        self.mod: ir.Module = module

    def __setitem__(self, key, value):
        self.values[key] = value

    def __getitem__(self, item):
        if item not in self.values.keys():
            ft = request_feature(self.mod, item)
            elmnt = ScopeElement(ft[1], ft[0])
            self.values[item] = elmnt
            return elmnt

        return self.values[item]

    def add_global(self, key, value):
        self.values[key] = value


def compile_ast(file_ast, filename):
    module = ir.Module(name=filename)

    types = {
        "int": ir.IntType(32),
        "float": ir.FloatType(),
        "double": ir.DoubleType(),
        "bool": ir.IntType(8),
        "str": ir.PointerType(),
        "ptr": ir.PointerType(),
        "list": ir.PointerType()
    }

    global_scope = GlobalScope(module)
    global_scope.values = types

    for expr in file_ast:
        if isinstance(expr, FunctionDefinition):
            function_definition(module, expr, global_scope)
        if isinstance(expr, ImportStmt):
            args = [global_scope[arg.tpe] for arg in expr.args if isinstance(arg, FuncArg)]
            if len(expr.args) > 0:
                va_args = isinstance(expr.args[-1], VAArgs)
            else:
                va_args = False

            tpe = ir.FunctionType(global_scope[expr.return_type] if expr.return_type else ir.VoidType(), args, va_args)
            func = ir.Function(module, tpe, name=expr.func_name)
            global_scope[expr.func_name] = ScopeElement("func", func)

        if isinstance(expr, GlobalStmt):
            for symbol in expr.names:
                if symbol in global_scope.keys(): global_scope[symbol].value.linkage = ''

    return module

from ctypes import CFUNCTYPE, c_int

def setup_default_compiler():
    global target_machine

    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()
    target = llvm.Target.from_default_triple()
    target_machine = target.create_target_machine()

def get_engine(module: ir.Module, modules = None):
    module.triple = llvm.get_default_triple()
    module.data_layout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"


    if not path.exists(path.join(os.getcwd(), "p2ctemp")):
        os.mkdir(path.join(os.getcwd(), "p2ctemp"))

    if modules:
        for mod in modules:
            mod.triple = llvm.get_default_triple()
            mod.data_layout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"

            mod_ir = str(mod)
            mod_ir = mod_ir.replace("ptr*", "ptr")

            ll = llvm.parse_assembly(mod_ir)
            ll.verify()

            with open(path.join(os.getcwd(), "p2ctemp", mod.name + ".ll"), "w") as f:
                f.write(mod_ir)


    llvm_ir = str(module)
    llvm_ir = llvm_ir.replace("ptr*", "ptr")

    mod = llvm.parse_assembly(llvm_ir)
    mod.verify()

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