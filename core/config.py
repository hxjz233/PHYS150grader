"""
Configuration management for the PHYS150 grading system.
"""
import os
import toml
from typing import Dict, Any, Optional


class ConfigManager:
    """Handles loading and managing configuration files."""
    
    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(__file__))
        self._config = None
        self._tester = None
    
    @property
    def config(self) -> Dict[str, Any]:
        """Load and cache the main config.toml file."""
        if self._config is None:
            config_path = os.path.join(self.base_dir, "config.toml")
            if os.path.exists(config_path):
                self._config = toml.load(config_path)
            else:
                self._config = {}
        return self._config
    
    @property
    def tester(self) -> Dict[str, Any]:
        """Load and cache the tester.toml file from homework directory."""
        if self._tester is None:
            self._tester = self._load_tester_toml()
        return self._tester
    
    def _load_tester_toml(self) -> Dict[str, Any]:
        """Load tester.toml from homework directory if specified."""
        homework_dir = self.config.get("homework_dir", None)
        if homework_dir:
            tester_path = os.path.join(homework_dir, "tester.toml")
            if os.path.exists(tester_path):
                return toml.load(tester_path)
        
        # Fallback to local tester.toml
        local_tester = os.path.join(self.base_dir, "tester.toml")
        if os.path.exists(local_tester):
            return toml.load(local_tester)
        
        return {"problem": []}
    
    def get_homework_dir(self) -> str:
        """Get the homework directory path."""
        return self.config.get("homework_dir", self.base_dir)
    
    def get_submissions_dir(self) -> str:
        """Get the submissions directory path."""
        homework_dir = self.get_homework_dir()
        return os.path.join(homework_dir, self.config.get("submissions_dir", "submissions"))
    
    def get_feedback_dir(self) -> str:
        """Get the feedback directory path."""
        homework_dir = self.get_homework_dir()
        return os.path.join(homework_dir, self.config.get("feedback_dir", "feedback"))
    
    def get_gradebook_path(self) -> str:
        """Get the gradebook file path."""
        return self.config.get("gradebook", "grade.csv")
    
    def get_timeout(self) -> int:
        """Get the execution timeout value."""
        return self.config.get("timeout", 3)
    
    def get_homework_title(self) -> str:
        """Get the homework title."""
        return self.config.get("homework_title", "New Assignment")