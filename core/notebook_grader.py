"""
Main grading logic for individual notebooks.
"""
import io
import os
import platform
from contextlib import redirect_stdout
from types import SimpleNamespace
from typing import Dict, Any, List, Tuple, Optional, Union

import nbformat

from .config import ConfigManager
from .test_runner import TestValidator, TestRunner
from .mock_system import MockManager

# Import appropriate run_cell function based on OS
if platform.system() == "Linux" or platform.system() == "Darwin":
    from safecode_unix import run_cell
else:
    from safecode import run_cell

from safecode import is_code_safe, sanitize_student_code


class NotebookGrader:
    """Main class for grading individual notebooks."""
    
    def __init__(self, config_manager: ConfigManager = None):
        self.config = config_manager or ConfigManager()
        self.validator = TestValidator()
        self.test_runner = TestRunner(self.validator)
        self.mock_manager = MockManager()
    
    def grade_notebook(self, nb: nbformat.NotebookNode = None) -> Tuple[Any, Optional[float], Optional[float], Optional[Dict]]:
        """Grade a notebook and return results."""
        if nb is None:
            return self._get_max_score_only()
        
        cell_count_result = self._validate_cell_count(nb)
        if cell_count_result:
            return cell_count_result
        
        return self._grade_all_problems(nb)
    
    def _get_max_score_only(self) -> Tuple[None, None, float, None]:
        """Return only the maximum possible score."""
        max_score = sum(p.get("pts", 1) for p in self.config.tester["problem"])
        return None, None, max_score, None
    
    def _validate_cell_count(self, nb: nbformat.NotebookNode) -> Optional[Tuple]:
        """Validate that the notebook has the expected number of code cells."""
        expected_code_cells = sum(p.get('next_code_cell', 0) for p in self.config.tester['problem'])
        
        # First count all code cells
        actual_code_cells = sum(1 for cell in nb.cells if cell.cell_type == 'code')
        
        if actual_code_cells != expected_code_cells:
            # Check if there's an empty cell at the end that we can ignore
            non_empty_code_cells = sum(1 for cell in nb.cells 
                                     if cell.cell_type == 'code' and cell.source.strip())
            
            # If we have the right number of non-empty code cells, proceed with grading
            if non_empty_code_cells == expected_code_cells:
                return None
                
            # Otherwise return the cell mismatch error
            cell_mismatch_result = [{
                'cell_index': 'ALL',
                'passed': 0,
                'total': 1,
                'score': 0.0,
                'pts': 0.0,
                'failed_tests': [f"Cell count mismatch: Expected {expected_code_cells} code cells, but found {actual_code_cells}"],
                'safety_violations': 0,
                'timeout_violations': 0,
                'cell_mismatch': True,
                'expected_cells': expected_code_cells,
                'actual_cells': actual_code_cells
            }]
            return cell_mismatch_result, None, None, None
        
        return None
    
    def _grade_all_problems(self, nb: nbformat.NotebookNode) -> Tuple[List[Dict], float, float, Dict]:
        """Grade all problems in the notebook."""
        results = []
        total_score = 0
        max_score = 0
        current_code_cell_index = 0
        test_results = {}
        
        for prob_idx, problem in enumerate(self.config.tester["problem"], 1):
            current_code_cell_index += problem["next_code_cell"]
            
            problem_result = self._grade_single_problem(
                problem, prob_idx, current_code_cell_index, nb
            )
            
            results.append(problem_result["result"])
            total_score += problem_result["score"]
            max_score += problem_result["max_score"]
            test_results.update(problem_result["test_results"])
        
        return results, total_score, max_score, test_results
    
    def _grade_single_problem(self, problem: Dict[str, Any], prob_idx: int, 
                             cell_index: int, nb: nbformat.NotebookNode) -> Dict[str, Any]:
        """Grade a single problem."""
        pts = problem.get("pts", 1)
        tests = problem["tests"]
        line_offset = problem.get("line_offset", 0)
        
        try:
            cell = self._get_code_cell_by_index(nb, cell_index)
        except IndexError as e:
            # Handle missing cell
            return {
                "result": self._create_problem_result(cell_index, 0, len(tests), 0, pts, [str(e)]),
                "score": 0,
                "max_score": pts,
                "test_results": {}
            }
        
        passed = 0
        failed_tests = []
        safety_violations = 0
        timeout_violations = 0
        test_results = {}
        
        for test_idx, test in enumerate(tests, 1):
            test_result = self._run_single_test(
                test, test_idx, prob_idx, problem, cell, line_offset
            )
            
            if test_result["passed"]:
                passed += 1
            else:
                failed_tests.append(test_result["failure_message"])
                if "blocked" in test_result["failure_message"].lower():
                    safety_violations += 1
                elif "timeout" in test_result["failure_message"].lower():
                    timeout_violations += 1
            
            key = f"prob{prob_idx}_test{test_idx}"
            test_results[key] = (1 if test_result["passed"] else 0, test_result["failure_message"])
        
        score = (passed / len(tests) * pts) if tests else 0
        
        return {
            "result": self._create_problem_result(
                cell_index, passed, len(tests), score, pts, failed_tests,
                safety_violations, timeout_violations
            ),
            "score": score,
            "max_score": pts,
            "test_results": test_results
        }
    
    def _run_single_test(self, test: Dict[str, Any], test_idx: int, prob_idx: int,
                        problem: Dict[str, Any], cell: nbformat.NotebookNode, 
                        line_offset: int) -> Dict[str, Any]:
        """Run a single test case."""
        # Set up test namespace
        test_ns = self._create_test_namespace(test)
        
        # Set up mocks
        self.mock_manager.setup_mocks(test_ns, test)
        
        # Prepare code
        code_to_run = self._prepare_code(cell, line_offset, test, problem)
        
        # Build input description for error messages
        input_str = self._build_input_description(test)
        
        # Check code safety
        safe, reason = is_code_safe(code_to_run)
        if not safe:
            return {
                "passed": False,
                "failure_message": f"Test {test_idx} blocked on input ({input_str}): {reason}"
            }
        
        # Execute code
        try:
            cell_output = self._execute_code(code_to_run, test_ns)
        except Exception as e:
            if str(e) == "__DEADLOOP__":
                return {
                    "passed": False,
                    "failure_message": f"Test {test_idx} timeout on input ({input_str})"
                }
            else:
                err_type = type(e).__name__
                return {
                    "passed": False,
                    "failure_message": f"Test {test_idx} error ({err_type}) on input ({input_str}): {e}"
                }
        
        # Validate results
        try:
            self.test_runner.run_test(test, test_ns, cell_output)
            return {"passed": True, "failure_message": ""}
        except AssertionError as e:
            return {
                "passed": False,
                "failure_message": f"Test {test_idx} failed on input ({input_str}): {e}"
            }
    
    def _create_test_namespace(self, test: Dict[str, Any]) -> SimpleNamespace:
        """Create and populate the test namespace."""
        test_ns = SimpleNamespace()
        
        # Set up test input variables
        test_inputs = test.get("variables", {})
        for var, val in test_inputs.items():
            val = self.validator._convert_complex_if_needed(val)
            # Create a new list if the value is a list to prevent modifying the original
            if isinstance(val, list):
                val = val.copy()
            setattr(test_ns, var, val)
        
        return test_ns
    
    def _prepare_code(self, cell: nbformat.NotebookNode, line_offset: int, 
                     test: Dict[str, Any], problem: Dict[str, Any]) -> str:
        """Prepare the student's code for execution."""
        # Extract code lines
        cell_lines = cell.source.splitlines() if isinstance(cell.source, str) else cell.source
        non_blank_lines = [line for line in cell_lines if line.strip() != ""]
        code_to_run = "\n".join(non_blank_lines[line_offset:])
        
        # Add prefix code if specified
        code_to_run = self._add_prefix_code(code_to_run, test, problem)
        
        # Sanitize code
        test_inputs = test.get("variables", {})
        input_overload = test.get("input_overload")
        
        if test_inputs and input_overload is None:
            # Remove input lines if we have test variables but no input overload
            from safecode import remove_input_lines
            code_to_run = remove_input_lines(code_to_run)
        
        code_to_run = sanitize_student_code(code_to_run)
        
        return code_to_run
    
    def _add_prefix_code(self, code_to_run: str, test: Dict[str, Any], 
                        problem: Dict[str, Any]) -> str:
        """Add prefix code if specified in test or problem configuration.
        
        Problem-level prefix code is applied first, followed by test-level prefix code
        if it exists. This allows test-specific code to override problem-level settings
        if needed.
        """
        all_prefix_lines = []
        
        # Add problem-level prefix code first
        if "prefix_code" in problem:
            prob_prefix = problem["prefix_code"]
            if isinstance(prob_prefix, str):
                all_prefix_lines.append(prob_prefix)
            else:
                all_prefix_lines.extend(prob_prefix)
        
        # Add test-level prefix code second (can override problem-level settings)
        if "prefix_code" in test:
            test_prefix = test["prefix_code"]
            if isinstance(test_prefix, str):
                all_prefix_lines.append(test_prefix)
            else:
                all_prefix_lines.extend(test_prefix)
        
        if all_prefix_lines:
            prefix_code = "\n".join(all_prefix_lines)
            code_to_run = prefix_code + "\n" + code_to_run
        
        return code_to_run
    
    def _build_input_description(self, test: Dict[str, Any]) -> str:
        """Build description string for input parameters in error messages."""
        formatted_inputs = []
        
        # Add test variables
        test_inputs = test.get("variables", {})
        for k, v in test_inputs.items():
            converted_v = self.validator._convert_complex_if_needed(v)
            formatted_inputs.append(f'{k}={converted_v}')
        
        input_str = ', '.join(formatted_inputs)
        
        # Add input overload description
        input_overload = test.get("input_overload")
        if input_overload is not None:
            overload_desc = self.mock_manager.get_input_description(input_overload)
            if input_str:
                input_str += f", {overload_desc}"
            else:
                input_str = overload_desc
        
        return input_str
    
    def _execute_code(self, code_to_run: str, test_ns: SimpleNamespace) -> str:
        """Execute the prepared code and capture output."""
        f = io.StringIO()
        with redirect_stdout(f):
            cell_result = run_cell(code_to_run, test_ns)
        
        if cell_result == "__DEADLOOP__":
            raise Exception("__DEADLOOP__")
        
        return f.getvalue()
    
    def _get_code_cell_by_index(self, nb: nbformat.NotebookNode, target_index: int) -> nbformat.NotebookNode:
        """Get a code cell by its accumulated index, skipping empty cells."""
        count = 0
        for cell in nb.cells:
            if cell.cell_type == "code" and cell.source.strip():
                count += 1
                if count == target_index:
                    return cell
        raise IndexError(f"Code cell number {target_index} not found.")
    
    def _create_problem_result(self, cell_index: int, passed: int, total: int, 
                              score: float, pts: float, failed_tests: List[str],
                              safety_violations: int = 0, timeout_violations: int = 0) -> Dict[str, Any]:
        """Create a standardized problem result dictionary."""
        return {
            "cell_index": cell_index,
            "passed": passed,
            "total": total,
            "score": score,
            "pts": pts,
            "failed_tests": failed_tests,
            "safety_violations": safety_violations,
            "timeout_violations": timeout_violations
        }