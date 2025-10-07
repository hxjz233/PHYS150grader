"""
Refactored gradecell.py - Main interface for notebook grading.
This file maintains backward compatibility while using the new class-based system.
"""
import os
import sys

# Add the core module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))

from core.config import ConfigManager
from core.notebook_grader import NotebookGrader

# Global instances for backward compatibility
_config_manager = ConfigManager()
_notebook_grader = NotebookGrader(_config_manager)

# Expose the tester configuration for backward compatibility
tester = _config_manager.tester

# Main functions for backward compatibility
def _to_complex_if_needed(val):
    """Converts a dict with 'real' and 'imag' keys to a complex number."""
    return _notebook_grader.validator._convert_complex_if_needed(val)

def check_test(test, test_ns, cell_output):
    """Check a test result - backward compatibility wrapper."""
    return _notebook_grader.test_runner.run_test(test, test_ns, cell_output)

def get_code_cell_by_accumulated_index(nb, target_index):
    """Get a code cell by accumulated index - backward compatibility wrapper."""
    return _notebook_grader._get_code_cell_by_index(nb, target_index)

def grade_notebook(nb=None):
    """Grade a notebook - main entry point."""
    return _notebook_grader.grade_notebook(nb)

if __name__ == "__main__":
    print("This module is intended to be imported and used by grader.py.")