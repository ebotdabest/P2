import sys
import os.path as p
from ast import parse_partial_context
from compiler import compile_ast, run_module, compile_module, get_engine
import subprocess as sp
import os

directory = sys.argv[1]

files = os.listdir(directory)
modules = []
for file in files:
    with open(os.path.join(os.getcwd(), directory, file)) as f:
        content = f.read()

    print(f"======[{file}]======")
    result = parse_partial_context(content)

    module = compile_ast(result, file)
    modules.append(module)

get_engine(modules[0], modules)

compiled_files = " ".join([os.path.join(os.getcwd(), "p2ctemp", f)
                           for f in os.listdir(os.path.join(os.getcwd(), "p2ctemp"))])
sp.run([f"{os.getcwd()}/compile_output", compiled_files])
sp.run(["clang++", "-fPIE", "-pie", "output.o", "-o", "program"])
print("COMPILED!")
# compile_module(module)
# func, engine = run_module(module)
# print(func())

# files = get_ast()
