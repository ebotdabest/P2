import sys
import os.path as p
from ast import parse_partial_context
from compiler import compile_ast, run_module

directory =sys.argv[0]
def crawl_directory(dir):
    ...

result = parse_partial_context("""
import user_input() -> int

def main() -> int:
    return -5
""")

# print(result[1].statements[1])

# parse_partial_context("""b: int = 2*12+5""")
# print(result[1].statements[1])
module = compile_ast(result)
print(module)
func, engine = run_module(module)
print(func())

# files = get_ast()
