import importlib
import inspect
import pkgutil

import snake_quest


def public_objects():
    """(name, object) for every module of the package and every public class, function, method and property in it."""
    for info in pkgutil.walk_packages(snake_quest.__path__, "snake_quest."):
        if info.name == "snake_quest.__main__":  # importing it runs the game
            continue
        module = importlib.import_module(info.name)
        yield info.name, module
        for name, obj in vars(module).items():
            if name.startswith("_") or getattr(obj, "__module__", None) != module.__name__:
                continue
            if inspect.isfunction(obj):
                yield f"{info.name}.{name}", obj
            elif inspect.isclass(obj):
                yield f"{info.name}.{name}", obj
                for attr, member in vars(obj).items():
                    if attr.startswith("_"):
                        continue
                    if isinstance(member, property) or inspect.isfunction(getattr(member, "__func__", member)):
                        yield f"{info.name}.{name}.{attr}", (obj, attr)


def documented(obj) -> bool:
    if isinstance(obj, tuple):  # a method or property: an override may rely on the docstring of what it overrides
        cls, attr = obj
        for base in cls.__mro__:
            member = vars(base).get(attr)
            if member is not None and (member.__doc__ if isinstance(member, property) else inspect.getdoc(member)):
                return True
        return False
    doc = inspect.getdoc(obj)
    # a dataclass without a docstring gets its signature as one
    return bool(doc) and not (inspect.isclass(obj) and doc.startswith(f"{obj.__name__}("))


def test_everything_public_is_documented():
    missing = [name for name, obj in public_objects() if not documented(obj)]
    assert not missing, f"no docstring: {', '.join(missing)}"
