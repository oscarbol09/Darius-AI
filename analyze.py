import ast
tree = ast.parse(open('main.py', encoding='utf-8').read())
for node in tree.body:
    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        print(f'{type(node).__name__}: {node.name} (line {node.lineno}-{node.end_lineno})')
