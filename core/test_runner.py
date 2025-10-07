"""
Test execution and validation for the PHYS150 grading system.
"""
import re
from string import Formatter
from typing import Dict, Any, List, Optional, Union
from types import SimpleNamespace


class TestValidator:
    """Handles validation of test results against expected outcomes."""
    
    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """Remove leading/trailing whitespace, collapse all whitespace to single space."""
        return re.sub(r'\s+', ' ', text.strip())
    
    def validate_variable_test(self, test: Dict[str, Any], test_ns: SimpleNamespace) -> None:
        """Validate a variable-type test."""
        tol = test.get("tol", None)
        for var, expected in test["expected"].items():
            expected = self._convert_complex_if_needed(expected)
            actual = getattr(test_ns, var, None)
            
            if tol is not None:
                self._validate_with_tolerance(var, expected, actual, tol)
            else:
                self._validate_exact_match(var, expected, actual)
    
    def validate_output_test(self, test: Dict[str, Any], test_ns: SimpleNamespace, 
                           cell_output: str) -> None:
        """Validate an output-type test."""
        # Use printed outputs if available (excludes input prompts)
        if hasattr(test_ns, 'printed_outputs') and test_ns.printed_outputs:
            test_output = '\n'.join(test_ns.printed_outputs)
        else:
            test_output = cell_output
        
        case_sensitive = test.get("case_sensitive", False)
        
        if "format" in test:
            self._validate_format_output(test, test_output, case_sensitive)
        elif isinstance(test["expected"], list):
            self._validate_list_output(test, test_output, case_sensitive)
        else:
            self._validate_string_output(test, test_output, case_sensitive)
    
    def _convert_complex_if_needed(self, val: Any) -> Any:
        """Convert a dict with 'real' and 'imag' keys to a complex number."""
        if isinstance(val, dict) and 'real' in val and 'imag' in val:
            return complex(val['real'], val['imag'])
        return val
    
    def _validate_with_tolerance(self, var: str, expected: Any, actual: Any, tol: float) -> None:
        """Validate values with tolerance for numeric types."""
        if not (isinstance(actual, (int, float, complex)) and 
                isinstance(expected, (int, float, complex))):
            raise AssertionError(f"test for {var} expected {expected}, got {actual} (non-numeric, cannot use tol)")
        
        if abs(actual - expected) > tol:
            raise AssertionError(f"test for {var} expected {expected} (tol={tol}), got {actual}")
    
    def _validate_exact_match(self, var: str, expected: Any, actual: Any) -> None:
        """Validate exact match between expected and actual values."""
        if actual != expected:
            raise AssertionError(f"test for {var} expected {expected}, got {actual}")
    
    def _validate_format_output(self, test: Dict[str, Any], test_output: str, 
                               case_sensitive: bool) -> None:
        """Validate output using format string matching."""
        fmt = test["format"]
        expected_vars = test.get("expected", {})
        tol = test.get("tol", None)
        
        # Build regex from format string
        regex = re.escape(fmt)
        for _, var, _, _ in Formatter().parse(fmt):
            if var:
                regex = regex.replace(r'\{' + var + r'\}', r'(?P<' + var + r'>.+)')
        regex = regex + r'\s*$'  # Allow trailing whitespace/newline at end
        
        re_flags = re.DOTALL if case_sensitive else (re.DOTALL | re.IGNORECASE)
        match = re.match(regex, self.normalize_whitespace(test_output), flags=re_flags)
        
        if not match:
            cs_hint = "(case-sensitive)" if case_sensitive else "(case-insensitive)"
            raise AssertionError(
                f"Output did not match expected format.\n"
                f"Expected format {cs_hint}: {fmt}\n"
                f"Actual: {test_output}"
            )
        
        # Compare extracted values to expected
        extracted = match.groupdict()
        for var, expected_val in expected_vars.items():
            actual_val = extracted.get(var, None)
            if actual_val is None:
                raise AssertionError(f"Variable {var} not found in output.")
            
            self._compare_extracted_values(var, expected_val, actual_val, tol)
    
    def _compare_extracted_values(self, var: str, expected_val: Any, 
                                 actual_val: str, tol: Optional[float]) -> None:
        """Compare extracted values from format string matching."""
        try:
            expected_num = float(expected_val)
            actual_num = float(actual_val)
            if tol is not None:
                if abs(actual_num - expected_num) > tol:
                    raise AssertionError(f"{var}: expected {expected_num} (tol={tol}), got {actual_num}")
            else:
                if actual_num != expected_num:
                    raise AssertionError(f"{var}: expected {expected_num}, got {actual_num}")
        except (ValueError, TypeError):
            # Fallback to string comparison
            if str(actual_val) != str(expected_val):
                raise AssertionError(f"{var}: expected '{expected_val}', got '{actual_val}'")
    
    def _validate_list_output(self, test: Dict[str, Any], test_output: str, 
                             case_sensitive: bool) -> None:
        """Validate output against a list of expected strings."""
        test_output_list = test_output if isinstance(test_output, list) else [test_output]
        
        for expected, actual in zip(test["expected"], test_output_list):
            normalized_actual = self.normalize_whitespace(actual)
            normalized_expected = self.normalize_whitespace(expected)
            
            if case_sensitive:
                if normalized_actual != normalized_expected:
                    raise AssertionError(f"test for output expected {expected}, got {actual} (case-sensitive)")
            else:
                if normalized_actual.lower() != normalized_expected.lower():
                    raise AssertionError(f"test for output expected {expected}, got {actual} (case-insensitive)")
    
    def _validate_string_output(self, test: Dict[str, Any], test_output: str, 
                               case_sensitive: bool) -> None:
        """Validate output against a single expected string."""
        normalized_output = self.normalize_whitespace(test_output)
        normalized_expected = self.normalize_whitespace(test["expected"])
        
        if case_sensitive:
            if normalized_output != normalized_expected:
                raise AssertionError(f"test for output expected {test['expected']}, got {test_output} (case-sensitive)")
        else:
            if normalized_output.lower() != normalized_expected.lower():
                raise AssertionError(f"test for output expected {test['expected']}, got {test_output} (case-insensitive)")


class TestRunner:
    """Handles the execution of individual tests."""
    
    def __init__(self, validator: TestValidator):
        self.validator = validator
    
    def run_test(self, test: Dict[str, Any], test_ns: SimpleNamespace, 
                 cell_output: str) -> None:
        """Run a single test and validate its results."""
        test_type = test.get("type", "unknown")
        
        if test_type == "variable":
            self.validator.validate_variable_test(test, test_ns)
        elif test_type == "output":
            self.validator.validate_output_test(test, test_ns, cell_output)
        else:
            raise ValueError(f"Unknown test type: {test_type}")