import nbformat
import toml
import sys
import os
from types import SimpleNamespace
import platform

# Import run_cell and is_code_safe depending on OS
if platform.system() == "Linux" or platform.system() == "Darwin":
    from safecode_unix import run_cell
else:
    from safecode import run_cell
from safecode import is_code_safe

# Load tester.toml from homework directory if specified
def get_tester_toml():
    config_path = os.path.join(os.path.dirname(__file__), "config.toml")
    if os.path.exists(config_path):
        config = toml.load(config_path)
        homework_dir = config.get("homework_dir", None)
        if homework_dir:
            tester_path = os.path.join(homework_dir, "tester.toml")
            if os.path.exists(tester_path):
                return toml.load(tester_path)
    # fallback to local
    return toml.load("tester.toml")

tester = get_tester_toml()

def check_test(test, test_ns, cell_output):
    if test["type"] == "variable":
        for var, expected in test["expected"].items():
            actual = test_ns.__dict__.get(var, None)
            assert actual == expected, f"test for {var} expected {expected}, got {actual}"
    elif test["type"] == "output":
        if isinstance(test["expected"], list):
            for expected, actual in zip(test["expected"], cell_output if isinstance(cell_output, list) else [cell_output]):
                assert actual == expected, f"test for {var} expected Output {expected}, got {actual}"
        else:
            assert cell_output == test["expected"], f"test for {var} expected Output {test['expected']}, got {cell_output}"
    else:
        raise ValueError("Unknown test type")

def get_code_cell_by_accumulated_index(nb, target_index):
    count = 0
    for cell in nb.cells:
        if cell.cell_type == "code":
            count += 1
            if count == target_index:
                return cell
    raise IndexError(f"Code cell number {target_index} not found.")

def grade_notebook(nb=None):
    if nb is None:
        return None, None, None
        # raise ValueError("No notebook provided for grading.")
    results = []
    total_score = 0
    max_score = 0
    current_code_cell_index = 0
    for problem in tester["problems"]:
        current_code_cell_index += problem["next_code_cell"]
        pts = problem.get("pts", 1)
        tests = problem["tests"]
        line_offset = problem.get("line_offset", 0)
        cell = get_code_cell_by_accumulated_index(nb, current_code_cell_index)
        passed = 0
        failed_tests = []
        safety_violation_count = 0
        timeout_violation_count = 0
        for test_num, test in enumerate(tests, 1):
            test_ns = SimpleNamespace()
            test_inputs = test.get("variables", {})
            for var, val in test_inputs.items():
                setattr(test_ns, var, val)
            if cell.cell_type == "code":
                # Only execute code after line_offset
                cell_lines = cell.source.splitlines() if isinstance(cell.source, str) else cell.source
                code_to_run = "\n".join(cell_lines[line_offset:])
                # Check code safety before running
                safe, reason = is_code_safe(code_to_run)
                input_str = ', '.join([f'{k}={v}' for k, v in test_inputs.items()])
                if not safe:
                    failed_tests.append(f"Test {test_num} blocked on input ({input_str}): {reason}")
                    safety_violation_count += 1
                    continue
                old_stdout = sys.stdout
                sys.stdout = temp_stdout = type('', (), {'write': lambda self, x: setattr(self, 'out', x)})()
                try:
                    try:
                        cell_result = run_cell(code_to_run, test_ns)
                        if cell_result == "__DEADLOOP__":
                            failed_tests.append(f"Test {test_num} timeout on input ({input_str})")
                            timeout_violation_count += 1
                            continue
                        cell_output = getattr(temp_stdout, 'out', None)
                    except Exception as exec_err:
                        err_type = type(exec_err).__name__
                        failed_tests.append(f"Test {test_num} error ({err_type}) on input ({input_str}): {exec_err}")
                        continue
                finally:
                    sys.stdout = old_stdout
                try:
                    check_test(test, test_ns, cell_output)
                    passed += 1
                except AssertionError as e:
                    failed_tests.append(f"Test {test_num} failed on input ({input_str}): {e}")
        percent = passed / len(tests) if tests else 0
        score = percent * pts
        total_score += score
        max_score += pts
        results.append({
            "cell_index": current_code_cell_index,
            "passed": passed,
            "total": len(tests),
            "score": score,
            "pts": pts,
            "failed_tests": failed_tests,
            "safety_violations": safety_violation_count,
            "timeout_violations": timeout_violation_count
        })
    return results, total_score, max_score

if __name__ == "__main__":
    print("This module is intended to be imported and used by grader.py.")
