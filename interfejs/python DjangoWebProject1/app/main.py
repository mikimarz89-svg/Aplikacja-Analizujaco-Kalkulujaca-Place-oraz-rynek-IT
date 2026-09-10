from typing import Any

def hello(name: str = "world") -> str:
    return f"Hello, {name}!"

def add(a: int, b: int) -> int:
    return a + b

# Tylko funkcje wymienione tutaj bêd¹ dostêpne z weba (bezpieczeñstwo!)
EXPOSED_FUNCTIONS = {
    'hello': hello,
    'add': add,
}