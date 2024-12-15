from typing import Callable

_function_registry: dict[str, Callable] = {}


def register[T: Callable](fun: T) -> T:
    _function_registry[fun.__name__] = fun
    return fun


def get_functions() -> list[Callable]:
    return list(_function_registry.values())


def call_function(name: str, /, **kwargs):
    function = _function_registry.get(name)
    if function is None:
        raise ValueError(f"Tool '{name}' not found.")
    return function(**kwargs)
