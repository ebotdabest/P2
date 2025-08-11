from llvmlite import ir

def generate_head(rt, va_args, *args):
    return ir.FunctionType(rt, args, va_args)

int_t = ir.IntType(32)
bool_t = ir.IntType(8)
bool_s_t = ir.IntType(1)
ptr = ir.PointerType()
void = ir.VoidType()

class TokenType(ir.types.Type):
    def __init__(self):
        self._name = "token"
        self._is_first_class = True

    def __str__(self):
        return self._name

    def __eq__(self, other):
        return isinstance(other, TokenType)

    def __hash__(self):
        return hash(self._name)


token_t = TokenType()
FUNCTIONS = {
    "__p2_make_string": (generate_head(ptr, True, int_t), "create_string_array", "str"),
    "__t__str__free": (generate_head(void, False, ptr), "__t__str__free", "func"),
    "__t__str____eq__": (generate_head(bool_t, False, ptr, ptr), "__t__str__eq__", "bool"),
    "__t__str__replace": (generate_head(ptr, False, ptr, ptr, ptr), "__t__str__replace", "str"),
    "__p2_make_vector": (generate_head(ptr, False, ir.IntType(64)), "vector_init", "list"),
    "__t__list__append": (generate_head(ptr, False, ptr, ptr), "vector_push_back", "ptr"),
    "__t__list____index__": (generate_head(ptr, False, ptr, int_t), "vector_index", "ptr"),
    "__t__list____set_element__": (generate_head(ptr, False, ptr, ptr, int_t), "vector_insert_into", "ptr"),
    "__p2_floor_div": (generate_head(int_t, False, int_t, int_t), "p2_floor", "int"),
    "__p2_mod_div": (generate_head(int_t, False, int_t, int_t), "p2_mod", "int"),
    "__t__list____len__": (generate_head(int_t, False, ptr), "vector_size", "int"),
    "|llvm.coro.id": (generate_head(token_t, False, int_t, ptr, ptr, ptr), "@llvm.coro.id", "token"),
    "|llvm.coro.alloc": (generate_head(bool_s_t, False, token_t), "@llvm.coro.alloc", "token"),
    "|llvm.coro.begin": (generate_head(ptr, False, token_t, ptr), "@llvm.coro.begin", "ptr"),
    "|llvm.coro.suspend": (generate_head(bool_t, False, token_t, bool_s_t), "@llvm.coro.suspend",
                           "bool"),
    "|llvm.coro.free": (generate_head(ptr, False, token_t, ptr), "@llvm.coro.free", "ptr"),
    "|llvm.coro.end": (generate_head(bool_s_t, False, ptr, bool_s_t, token_t), "@llvm.coro.end",
                       "bool"),
    "|llvm.coro.promise": (generate_head(ptr, False, ptr, int_t, bool_s_t), "@llvm.coro.promise", "ptr")
}

def request_feature(module: ir.Module, name):
    """
    Requests a backend function for easier to read and less bloated llvm ir
    :param module: the module used for the ir
    :param name: the name of the feature
    :return:
    """
    head = FUNCTIONS[name]
    for func in module.functions:
        if func.name == head[1]:
            return func, head[2]

    return ir.Function(module, head[0], head[1]), head[2]

# global_scope = {} | types
    # global_scope["__p2_floor_div"] = ScopeElement("int", floor_div)
    # global_scope["__p2_mod_div"] = ScopeElement("int", mod_div)
    # global_scope["__p2_make_string"] = ScopeElement("str", make_str)
    # global_scope["__p2_make_vector"] = ScopeElement("list", vector_make)
    # global_scope["__t__str__free__"] = ScopeElement("func", free_str)
    # global_scope["__t__file__free__"] = ScopeElement("func", close_file)
    # global_scope["__t__str____eq__"] = ScopeElement("bool", str_check)
    # global_scope["__t__str__replace"] = ScopeElement("str", str_replace)
    # global_scope["__t__list__append"] = ScopeElement("ptr", vector_append)
    # global_scope["__t__list____index__"] = ScopeElement("ptr", vector_index)
