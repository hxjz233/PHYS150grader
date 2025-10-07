# PHYS150 Grader - Modular Architecture

A Python-based Jupyter notebook autograder for the PHYS 150 course with modular, class-based architecture. This system reads student submissions, executes test cases defined in TOML configuration files, and generates grades and feedback.

## Architecture Overview

The grading system uses a modular class-based architecture organized into core modules and main application files:

### Core Modules (`core/`)

- **`config.py`**: `ConfigManager` - Centralized configuration management for TOML files
- **`test_runner.py`**: `TestValidator` and `TestRunner` - Test execution and validation logic
- **`mock_system.py`**: `IOSpy` and `MockManager` - Input/output mocking and separation
- **`notebook_grader.py`**: `NotebookGrader` - Main grading orchestration

### Main Application Files

- **`gradecell.py`**: Single notebook grading interface
- **`grader.py`**: Batch grading system using `GradingSession` class
- **`feedback.py`**: Canvas feedback upload using `CanvasFeedbackUploader` class
- **`manual.py`**: Manual grading and feedback generation functions
- **`preprocess.py`**: Submission preprocessing using `SubmissionPreprocessor` class

## API Usage

### Single Notebook Grading
```python
from gradecell import grade_notebook
import nbformat

# Load notebook
nb = nbformat.read("student_notebook.ipynb", as_version=4)

# Grade the notebook
results, total_score, max_score, test_results = grade_notebook(nb)
```

### Batch Grading
```python
from grader import GradingSession

# Create and run grading session
session = GradingSession()
session.grade_all_students()
```

### Canvas Feedback Upload
```python
from feedback import CanvasFeedbackUploader

# Upload all feedback to Canvas
uploader = CanvasFeedbackUploader()
uploader.upload_all_feedback()
```

### Manual Grading
```python
from manual import generate_manual_feedback, update_gradebook

# Generate feedback from test results
user_grades, max_score = generate_manual_feedback()

# Update gradebook
update_gradebook(user_grades, max_score)
```

### Submission Preprocessing
```python
from preprocess import SubmissionPreprocessor

# Extract and rename submissions
preprocessor = SubmissionPreprocessor()
preprocessor.extract_submissions()
preprocessor.validate_extractions()
```

## Configuration

The system uses TOML configuration files:

### `config.toml` - Main Configuration
- `homework_dir`: Directory for current assignment files
- `submissions_dir`: Subdirectory for extracted student submissions
- `feedback_dir`: Subdirectory for generated feedback files
- `course_number`: Canvas course ID
- `homework_title`: Assignment name for gradebook
- `gradebook`: Path to Canvas gradebook CSV file
- `timeout`: Cell execution timeout (seconds)
- `debug`: Suppress actual feedback submission
- `headless`: Run browser in headless mode

### `tester.toml` - Test Definitions
- `next_code_cell`: Index of student solution cell
- `pts`: Points assigned to problem
- `line_offset`: Lines to skip in solution cell
- `tests`: Array of test definitions
  - `type`: "variable" or "output"
  - `variables`: Input variables for test
  - `expected`: Expected result
  - `tol`: Tolerance for numeric comparisons
  - `format`: Output format pattern (for output tests)
  - `case_sensitivity`: Case-sensitive matching

## Workflow

1. **Setup**: Export gradebook from Canvas, place submissions.zip in homework directory
2. **Preprocess**: Run `python preprocess.py` to extract submissions
3. **Grade**: Run `python grader.py` to grade all students
4. **Review**: Examine results in feedback directory and grading summary
5. **Upload**: Run `python feedback.py` to upload feedback to Canvas

## Key Features

### Safety and Security
- Code execution timeout protection
- Safety checking for dangerous operations
- Input/output separation and mocking
- Comprehensive error handling

### Test Types
- **Variable Tests**: Compare student variables with expected values
- **Output Tests**: Match printed output against patterns
- **Tolerance Support**: Numeric comparisons with configurable tolerance
- **Complex Number Support**: Automatic complex number handling

### Error Handling
- Safety violations (unsafe code patterns)
- Timeout violations (infinite loops)
- Execution errors (runtime exceptions)
- Cell count mismatches
- Unreadable notebooks

### Reporting
- Individual student feedback files
- Grading summary with statistics
- Wrong answer compilation
- Updated gradebook for Canvas import

## Class Hierarchy

```
ConfigManager
├── Loads and manages TOML configuration
└── Provides path resolution and settings access

TestValidator & TestRunner
├── Validates variable tests (tolerance, complex numbers)
├── Validates output tests (format matching, content)
└── Executes tests with safety checks and timeouts

IOSpy & MockManager
├── Creates spy functions for input/output separation
└── Manages mock environments for safe code execution

NotebookGrader
├── Orchestrates the grading process
├── Uses TestRunner for individual tests
└── Aggregates results and handles scoring

GradingSession
├── Manages batch grading for multiple students
├── Uses NotebookGrader for individual notebooks
└── Generates reports and updates gradebooks

CanvasFeedbackUploader
├── Handles Canvas authentication and navigation
├── Uploads feedback files to student assignments
└── Supports debug mode and headless operation

SubmissionPreprocessor
├── Extracts student submissions from zip files
├── Handles Canvas filename formats (including LATE submissions)
└── Validates extracted files
```

## Environment Requirements

- Python 3.7+
- nbformat: Jupyter notebook processing
- toml: Configuration file parsing
- selenium: Web automation for Canvas
- Chrome browser: For Canvas interaction

## Development Notes

The system maintains backward compatibility while providing a clean, modular architecture for easy maintenance and extension. Each class has a single responsibility and clear interfaces, making it easy to add new features or modify existing behavior.