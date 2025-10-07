"""
Preprocessing system for student submissions using the new modular architecture.
"""
import zipfile
import os
import sys

# Add the core module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))

from core.config import ConfigManager


class SubmissionPreprocessor:
    """Handles preprocessing of student submission zip files."""
    
    def __init__(self, config_manager: ConfigManager = None):
        self.config = config_manager or ConfigManager()
        self.homework_dir = self.config.get_homework_dir()
        self.submissions_dir = self.config.get_submissions_dir()
        self.zip_path = os.path.join(self.homework_dir, "submissions.zip")
    
    def extract_submissions(self) -> None:
        """Extract and rename student submissions from zip file."""
        # Ensure output directory exists
        os.makedirs(self.submissions_dir, exist_ok=True)
        
        if not os.path.exists(self.zip_path):
            raise FileNotFoundError(f"Submissions zip file not found: {self.zip_path}")
        
        extracted_count = 0
        
        with zipfile.ZipFile(self.zip_path, 'r') as zipf:
            for name in zipf.namelist():
                if name.endswith('.ipynb'):
                    user_id = self._extract_user_id(name)
                    if user_id:
                        new_name = f"{user_id}.ipynb"
                        output_path = os.path.join(self.submissions_dir, new_name)
                        
                        # Extract and save with new name
                        data = zipf.read(name)
                        with open(output_path, 'wb') as f:
                            f.write(data)
                        
                        extracted_count += 1
                        print(f"Extracted: {name} -> {new_name}")
                    else:
                        print(f"Warning: Could not extract user ID from {name}")
        
        print(f"Preprocessing complete. Extracted {extracted_count} submissions to {self.submissions_dir}")
    
    def _extract_user_id(self, filename: str) -> str:
        """Extract user ID from Canvas submission filename."""
        # Canvas submission format: prefix_[LATE_]userID_suffix.ipynb
        parts = filename.split('_')
        
        if len(parts) < 3:
            return ""
        
        # Handle late submissions: prefix_LATE_userID_suffix.ipynb
        if len(parts) >= 4 and parts[1] == "LATE":
            return parts[2]
        # Handle regular submissions: prefix_userID_suffix.ipynb
        else:
            return parts[1]
    
    def validate_extractions(self) -> None:
        """Validate that extractions were successful."""
        if not os.path.exists(self.submissions_dir):
            print("Warning: Submissions directory does not exist")
            return
        
        submissions = [f for f in os.listdir(self.submissions_dir) if f.endswith('.ipynb')]
        
        if not submissions:
            print("Warning: No .ipynb files found in submissions directory")
            return
        
        print(f"Found {len(submissions)} submissions:")
        for submission in sorted(submissions):
            user_id = os.path.splitext(submission)[0]
            filepath = os.path.join(self.submissions_dir, submission)
            file_size = os.path.getsize(filepath)
            print(f"  {user_id}: {file_size} bytes")


def main():
    """Main entry point for preprocessing."""
    preprocessor = SubmissionPreprocessor()
    
    print("Starting submission preprocessing...")
    preprocessor.extract_submissions()
    
    print("\nValidating extractions...")
    preprocessor.validate_extractions()


if __name__ == "__main__":
    main()