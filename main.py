import sys
import os.path as p
from ast import parse_partial_context
from compiler import compile_ast, run_module, compile_module, get_engine
import subprocess as sp
import os
directory =sys.argv[0]

with open("test.p2") as f:
    content = f.read()

result = parse_partial_context(content)

# print(result[1].statements[1])

# parse_partial_context("""b: int = 2*12+5""")
# print(result[1].statements[1])
module = compile_ast(result)
print(module)
get_engine(module)
sp.run([f"{os.getcwd()}/compile_output"])


# compile_module(module)
# func, engine = run_module(module)
# print(func())

# files = get_ast()
