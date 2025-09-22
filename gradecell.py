import nbformat
import toml
import sys
import os
import io
from contextlib import redirect_stdout
from types import SimpleNamespace
import platform

# Import run_cell and is_code_safe depending on OS
if platform.system() == "Linux" or platform.system() == "Darwin":
    from safecode_unix import run_cell
else:
    from safecode import run_cell
from safecode import is_code_safe, remove_input_lines

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

def _to_complex_if_needed(val):
    """Converts a dict with 'real' and 'imag' keys to a complex number."""
    if isinstance(val, dict) and 'real' in val and 'imag' in val:
        return complex(val['real'], val['imag'])
    return val

def check_test(test, test_ns, cell_output):
    if test["type"] == "variable":
        tol = test.get("tol", None)
        for var, expected in test["expected"].items():
            expected = _to_complex_if_needed(expected)  # Convert expected value
            actual = test_ns.__dict__.get(var, None)
            if tol is not None:
                # Try to compare as floats/complex with tolerance
                try:
                    if isinstance(actual, (int, float, complex)) and isinstance(expected, (int, float, complex)):
                        assert abs(actual - expected) <= tol, f"test for {var} expected {expected} (tol={tol}), got {actual}"
                    else:
                        raise AssertionError(f"test for {var} expected {expected}, got {actual} (non-numeric, cannot use tol)")
                except Exception as e:
                    raise AssertionError(str(e))
            else:
                assert actual == expected, f"test for {var} expected {expected}, got {actual}"
    elif test["type"] == "output":
        import re
        from string import Formatter
        def normalize(s):
            # Remove leading/trailing whitespace, collapse all whitespace (including newlines) to single space
            return re.sub(r'\s+', ' ', s.strip())

        case_sensitive = test.get("case_sensitive", False)
        re_flags = re.DOTALL if case_sensitive else (re.DOTALL | re.IGNORECASE)

        if "format" in test:
            fmt = test["format"]
            expected_vars = test.get("expected", {})
            tol = test.get("tol", None)
            # Build regex from format string
            regex = re.escape(fmt)
            # Replace {var} with regex group
            for _, var, _, _ in Formatter().parse(fmt):
                if var:
                    regex = regex.replace(r'\{' + var + r'\}', r'(?P<' + var + r'>.+)')
            regex = regex + r'\s*$'  # Allow trailing whitespace/newline at end
            match = re.match(regex, normalize(cell_output), flags=re_flags)
            if not match:
                cs_hint = "(case-sensitive)" if case_sensitive else "(case-insensitive)"
                raise AssertionError(f"Output did not match expected format.\nExpected format {cs_hint}: {fmt}\nActual: {cell_output}")
            extracted = match.groupdict()
            # Compare extracted values to expected
            for var, expected_val in expected_vars.items():
                actual_val = extracted.get(var, None)
                assert actual_val is not None, f"Variable {var} not found in output."
                # Try to compare as float if both are numeric
                try:
                    expected_num = float(expected_val)
                    actual_num = float(actual_val)
                    if tol is not None:
                        assert abs(actual_num - expected_num) <= tol, f"{var}: expected {expected_num} (tol={tol}), got {actual_num}"
                    else:
                        assert actual_num == expected_num, f"{var}: expected {expected_num}, got {actual_num}"
                except Exception:
                    # Fallback to string comparison
                    assert str(actual_val) == str(expected_val), f"{var}: expected '{expected_val}', got '{actual_val}'"
        elif isinstance(test["expected"], list):
            for expected, actual in zip(test["expected"], cell_output if isinstance(cell_output, list) else [cell_output]):
                if case_sensitive:
                    assert normalize(actual) == normalize(expected), f"test for output expected {expected}, got {actual} (case-sensitive)"
                else:
                    assert normalize(actual).lower() == normalize(expected).lower(), f"test for output expected {expected}, got {actual} (case-insensitive)"
        else:
            if case_sensitive:
                assert normalize(cell_output) == normalize(test["expected"]), f"test for output expected {test['expected']}, got {cell_output} (case-sensitive)"
            else:
                assert normalize(cell_output).lower() == normalize(test["expected"]).lower(), f"test for output expected {test['expected']}, got {cell_output} (case-insensitive)"
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
        # This case is for when grade_notebook is called to get max_score without a notebook
        max_score = sum(p.get("pts", 1) for p in tester["problem"])
        return None, None, max_score, None

    # --- Cell count check ---
    expected_code_cells = sum(p.get('next_code_cell', 0) for p in tester['problem'])
    actual_code_cells = sum(1 for cell in nb.cells if cell.cell_type == 'code')
    if actual_code_cells != expected_code_cells:
        test_results = {"expected": expected_code_cells, "got": actual_code_cells}
        return "CELL_MISMATCH", None, None, test_results

    results = []
    total_score = 0
    max_score = 0
    current_code_cell_index = 0
    test_results = {}  # key: prob#_test#, value: (1/0, failmsg)
    for prob_idx, problem in enumerate(tester["problem"], 1):
        current_code_cell_index += problem["next_code_cell"]
        pts = problem.get("pts", 1)
        tests = problem["tests"]
        line_offset = problem.get("line_offset", 0)
        cell = get_code_cell_by_accumulated_index(nb, current_code_cell_index)
        passed = 0
        failed_tests = []
        safety_violation_count = 0
        timeout_violation_count = 0
        for test_idx, test in enumerate(tests, 1):
            test_ns = SimpleNamespace()
            test_inputs = test.get("variables", {})
            for var, val in test_inputs.items():
                val = _to_complex_if_needed(val)  # Convert input variable
                setattr(test_ns, var, val)
            key = f"prob{prob_idx}_test{test_idx}"
            if cell.cell_type == "code":
                # Remove all blank lines first
                cell_lines = cell.source.splitlines() if isinstance(cell.source, str) else cell.source
                non_blank_lines = [line for line in cell_lines if line.strip() != ""]
                # Only execute code after line_offset
                code_to_run = "\n".join(non_blank_lines[line_offset:])
                # If test has inputs, we shouldn't be using student's input() calls
                if test_inputs:
                    code_to_run = remove_input_lines(code_to_run)
                # Check code safety before running
                safe, reason = is_code_safe(code_to_run)
                input_str = ', '.join([f'{k}={v}' for k, v in test_inputs.items()])
                if not safe:
                    failed_tests.append(f"Test {test_idx} blocked on input ({input_str}): {reason}")
                    safety_violation_count += 1
                    test_results[key] = (0, f"Blocked: {reason}")
                    continue
                f = io.StringIO()
                try:
                    with redirect_stdout(f):
                        cell_result = run_cell(code_to_run, test_ns)
                    if cell_result == "__DEADLOOP__":
                        failed_tests.append(f"Test {test_idx} timeout on input ({input_str})")
                        timeout_violation_count += 1
                        test_results[key] = (0, "Timeout")
                        continue
                    cell_output = f.getvalue()
                except Exception as exec_err:
                    err_type = type(exec_err).__name__
                    failmsg = f"Test {test_idx} error ({err_type}) on input ({input_str}): {exec_err}"
                    failed_tests.append(failmsg)
                    test_results[key] = (0, failmsg)
                    continue
                try:
                    check_test(test, test_ns, cell_output)
                    passed += 1
                    test_results[key] = (1, "")
                except AssertionError as e:
                    failmsg = f"Test {test_idx} failed on input ({input_str}): {e}"
                    failed_tests.append(failmsg)
                    test_results[key] = (0, failmsg)
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
    return results, total_score, max_score, test_results

if __name__ == "__main__":
    print("This module is intended to be imported and used by grader.py.")
