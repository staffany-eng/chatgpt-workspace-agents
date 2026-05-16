from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any


class FakeMCP:
    def __init__(self, *args: Any, **kwargs: Any):
        self.args = args
        self.kwargs = kwargs
        self.tools = []

    def tool(self):
        def decorate(func):
            self.tools.append(func)
            return func

        return decorate

    def run(self, *args: Any, **kwargs: Any):
        return None


def install_fake_mcp() -> None:
    sys.modules["mcp"] = types.ModuleType("mcp")
    sys.modules["mcp.server"] = types.ModuleType("mcp.server")
    fastmcp = types.ModuleType("mcp.server.fastmcp")
    fastmcp.FastMCP = FakeMCP
    sys.modules["mcp.server.fastmcp"] = fastmcp


def load_mcp_module(filename: str, module_name: str | None = None):
    install_fake_mcp()
    module_path = Path(__file__).with_name(filename)
    module_dir = str(module_path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)

    name = module_name or f"{module_path.stem}_under_test"
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

