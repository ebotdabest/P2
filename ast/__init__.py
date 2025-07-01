from antlr4 import *
from ast.gen.PythonLexer import PythonLexer
from ast.gen.PythonParser import PythonParser
from ast.gen.PythonParserVisitor import PythonParserVisitor

from .pvisitor import P2Visitor

def parse_partial_context(code):
    input_stream = InputStream(code)

    lexer = PythonLexer(input_stream)
    token_stream = CommonTokenStream(lexer)
    parser = PythonParser(token_stream)
    tree = parser.file_input()

    print(tree.toStringTree(recog=parser))

    visitor = P2Visitor()
    visitor.visit(tree)

    return visitor.read_result()