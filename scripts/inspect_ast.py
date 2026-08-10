import ast

# Inspect ghost_fill_cleaner.py
print("=== ghost_fill_cleaner.py ===")
tree = ast.parse(open('ghost_fill_cleaner.py').read())
for n in ast.walk(tree):
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        print(f"  L{n.lineno}: {type(n).__name__} {n.name}")
    elif isinstance(n, ast.ImportFrom):
        print(f"  L{n.lineno}: from {n.module} import {[a.name for a in n.names]}")

print()
print("=== ghost_fill_engine.py ===")
tree2 = ast.parse(open('trading_platform/services/ghost_fill_engine.py').read())
for n in ast.walk(tree2):
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        print(f"  L{n.lineno}: {type(n).__name__} {n.name}")
