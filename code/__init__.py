"""Evaluation pipeline package."""

import importlib.util
import os

# Prevent shadowing standard library 'code' module when current directory is in sys.path
_stdlib_code_path = os.path.join(os.path.dirname(os.__file__), "code.py")
if os.path.exists(_stdlib_code_path):
    _spec = importlib.util.spec_from_file_location("_stdlib_code", _stdlib_code_path)
    if _spec and _spec.loader:
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        for _attr in dir(_mod):
            if not _attr.startswith("__"):
                globals()[_attr] = getattr(_mod, _attr)
