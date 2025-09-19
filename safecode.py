import sys
from types import SimpleNamespace
import multiprocessing
import toml

# Read timeout from config.toml
import os
config_path = os.path.join(os.path.dirname(__file__), "config.toml")
if os.path.exists(config_path):
    config = toml.load(config_path)
    TIMEOUT = config.get("timeout", 3)
else:
    TIMEOUT = 3

# previous code that used multiprocessing for timeout. Now disabled due to PicklingError when student code contains function, class, etc.
# def _exec_code(cell_code, ns_dict, queue):
#     try:
#         exec(cell_code, ns_dict)
#         queue.put(ns_dict)
#     except Exception as e:
#         queue.put(e)

# def run_cell(cell_code, test_ns):
#     # If code contains a function definition, use exec directly to avoid PicklingError
#     if "def " in cell_code:
#         try:
#             exec(cell_code, test_ns.__dict__)
#         except Exception as e:
#             raise e
#         return None
#     # Otherwise, use multiprocessing to enforce timeout
#     manager = multiprocessing.Manager()
#     queue = manager.Queue()
#     p = multiprocessing.Process(target=_exec_code, args=(cell_code, test_ns.__dict__, queue))
#     p.start()
#     p.join(TIMEOUT)
#     if p.is_alive():
#         p.terminate()
#         # Instead of raising, return a special marker for timeout
#         return "__DEADLOOP__"
#     result = queue.get() if not queue.empty() else None
#     if isinstance(result, Exception):
#         raise result
#     if isinstance(result, dict):
#         test_ns.__dict__.update(result)

def run_cell(cell_code, test_ns):
    try:
        exec(cell_code, test_ns.__dict__)
    except Exception as e:
        raise e
    return None

def is_code_safe(cell_code):
    banned_imports = ["os", "sys", "subprocess", "socket", "shutil", "pathlib", "requests", "multiprocessing", "threading", "ctypes", "pickle"]
    banned_patterns = ["open(", "eval(", "exec(", "__import__", "compile(", "globals(", "locals(", "setattr(", "delattr(", "getattr(", "exit(", "quit(", "system(", "fork(", "kill(", "remove(", "rmdir(", "unlink(", "chmod(", "chown(", "popen(", "walk(", "makedirs(", "mkdir(", "rmtree(", "copy(", "move(", "rename(", "socket.", "threading.", "multiprocessing."]
    for imp in banned_imports:
        if f"import {imp}" in cell_code or f"from {imp} import" in cell_code:
            return False, f"Banned import detected: {imp}"
    for pat in banned_patterns:
        if pat in cell_code:
            return False, f"Banned code pattern detected: {pat}"
    return True, ""

def remove_input_lines(code_string):
    """Removes lines containing 'input(' from a code string."""
    lines = code_string.splitlines()
    filtered_lines = [line for line in lines if 'input(' not in line]
    return "\n".join(filtered_lines)
