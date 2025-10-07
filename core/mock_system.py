"""
Mock system for input/output during test execution.
"""
import io
from typing import List, Any, Callable, Optional
from types import SimpleNamespace


class IOSpy:
    """Spy system to capture and separate input prompts from print outputs."""
    
    def __init__(self, test_ns: SimpleNamespace):
        self.test_ns = test_ns
        self.test_ns.prompts_used = []
        self.test_ns.printed_outputs = []
        self._original_print = print
    
    def create_spy_print(self) -> Callable:
        """Create a spy version of print that captures output."""
        def spy_print(*args, **kwargs):
            # Reconstruct the message as a single string
            output = io.StringIO()
            kwargs['file'] = output
            self._original_print(*args, **kwargs)
            message = output.getvalue()
            
            # Remove trailing newline that print adds, to match user expectation
            if message.endswith('\n'):
                message = message[:-1]
            
            self.test_ns.printed_outputs.append(message)
            # Also call original print to ensure it's captured by redirect_stdout
            self._original_print(*args)
        
        return spy_print
    
    def create_spy_input(self, input_overload: Any) -> Callable:
        """Create a spy version of input based on the overload type."""
        if isinstance(input_overload, list):
            return self._create_list_input_spy(input_overload)
        else:
            return self._create_single_input_spy(input_overload)
    
    def _create_list_input_spy(self, input_list: List[Any]) -> Callable:
        """Create input spy that returns values from a list in sequence."""
        inputs_iterator = iter(input_list)
        
        def spy_input_from_list(prompt=""):
            self.test_ns.prompts_used.append(prompt)
            self._original_print(prompt, end="")  # So it appears in cell_output
            try:
                return str(next(inputs_iterator))
            except StopIteration:
                return ""
        
        return spy_input_from_list
    
    def _create_single_input_spy(self, input_value: Any) -> Callable:
        """Create input spy that returns the same value every time."""
        def spy_input_single(prompt=""):
            self.test_ns.prompts_used.append(prompt)
            self._original_print(prompt, end="")  # So it appears in cell_output
            return str(input_value)
        
        return spy_input_single


class MockManager:
    """Manages the setup of mock functions for test execution."""
    
    def __init__(self):
        self.spy = None
    
    def setup_mocks(self, test_ns: SimpleNamespace, test_config: dict) -> None:
        """Set up mock functions based on test configuration."""
        self.spy = IOSpy(test_ns)
        
        # Always set up print spy
        test_ns.print = self.spy.create_spy_print()
        
        # Set up input mock if specified
        input_overload = test_config.get("input_overload")
        if input_overload is not None:
            test_ns.input = self.spy.create_spy_input(input_overload)
    
    def get_input_description(self, input_overload: Any) -> str:
        """Generate a description string for input overload in error messages."""
        if input_overload is not None:
            return f"all inputs be {repr(input_overload)}"
        return ""