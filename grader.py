"""
Batch grading system for PHYS150 assignments.
"""
import csv
import os
import sys
from collections import defaultdict
from typing import List, Dict, Any, Tuple, Optional

import nbformat

# Add the core module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))

from core.config import ConfigManager
from core.notebook_grader import NotebookGrader


class GradingSession:
    """Manages a complete grading session for multiple students."""
    
    def __init__(self, config_manager: ConfigManager = None):
        self.config = config_manager or ConfigManager()
        self.notebook_grader = NotebookGrader(self.config)
        
        # Grading session state
        self.user_grades = {}
        self.user_grades_percentage = {}
        self.summary_scores = defaultdict(list)
        self.safety_violations = defaultdict(int)
        self.timeout_violations = defaultdict(int)
        self.safety_violation_details = []
        self.timeout_violation_details = []
        self.exec_err_details = []
        self.exec_err_counts = defaultdict(int)
        self.unreadable_notebooks = []
        self.cell_mismatch_users = []
        self.wa_lines = []
    
    def grade_all_students(self) -> None:
        """Grade all students and generate reports."""
        print("Starting grading session...")
        
        userids = self._get_student_ids()
        test_keys = self._generate_test_keys()
        
        passfail_rows, msg_rows, userids_done = self._grade_students(userids, test_keys)
        
        self._write_test_results(test_keys, passfail_rows, msg_rows)
        self._write_wrong_answers()
        self._write_summary_metadata()
        self._update_gradebook(userids_done)
        
        print(f"Grading complete. Processed {len(userids_done)} students.")
    
    def _get_student_ids(self) -> List[str]:
        """Get sorted list of student IDs from gradebook."""
        gradebook_path = self.config.get_gradebook_path()
        userids = []
        
        with open(gradebook_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                id_val = row.get("ID")
                if id_val and id_val.strip():
                    userids.append(id_val.strip())
        
        return sorted(userids, key=lambda x: int(x) if x.isdigit() else x)
    
    def _generate_test_keys(self) -> List[str]:
        """Generate test keys for CSV headers."""
        test_keys = []
        for prob_idx, problem in enumerate(self.config.tester["problem"], 1):
            for test_idx, _ in enumerate(problem["tests"], 1):
                test_keys.append(f"prob{prob_idx}_test{test_idx}")
        return test_keys
    
    def _grade_students(self, userids: List[str], test_keys: List[str]) -> Tuple[List, List, List]:
        """Grade all students and collect results."""
        passfail_rows = []
        msg_rows = []
        userids_done = []
        
        for userid in userids:
            print(f"Grading student {userid}...")
            
            try:
                results, total_score, max_score, test_results = self._grade_single_student(userid)
            except Exception as e:
                print(f"Error grading notebook for user {userid}: {e}")
                results, total_score, max_score, test_results = None, None, None, None
            
            if results == "CELL_MISMATCH":
                self.cell_mismatch_users.append(f"User: {userid}, Expected: {test_results['expected']}, Got: {test_results['got']}")
                continue
            
            if results is None or test_results is None:
                self.unreadable_notebooks.append(userid)
                continue
            
            self._write_student_feedback(userid, results, total_score, max_score)
            self._record_student_grade(userid, total_score, max_score)
            self._add_test_results_to_csv(userid, test_keys, test_results, passfail_rows, msg_rows)
            self._collect_summary_statistics(userid, results)
            
            userids_done.append(userid)
        
        return passfail_rows, msg_rows, userids_done
    
    def _grade_single_student(self, userid: str) -> Tuple[Any, Any, Any, Any]:
        """Grade a single student's notebook."""
        nb_path = os.path.join(self.config.get_submissions_dir(), f"{userid}.ipynb")
        
        if not os.path.exists(nb_path):
            return None, None, None, None
        
        try:
            nb = nbformat.read(open(nb_path, encoding="utf-8"), as_version=4)
            return self.notebook_grader.grade_notebook(nb)
        except Exception as e:
            print(f"Failed to read/grade notebook {nb_path}: {e}")
            return None, None, None, None
    
    def _write_student_feedback(self, userid: str, results: List[Dict], 
                               total_score: float, max_score: float) -> None:
        """Write individual student feedback file."""
        feedback_dir = self.config.get_feedback_dir()
        txt_path = os.path.join(feedback_dir, f"{userid}.txt")
        os.makedirs(feedback_dir, exist_ok=True)
        
        with open(txt_path, "w", encoding="utf-8") as f:
            for res in results:
                f.write(f"Cell {res['cell_index']}: {res['passed']}/{res['total']} tests passed, "
                       f"Score: {res['score']:.2f}/{res['pts']}\n")
                
                if res['failed_tests']:
                    f.write("  Failed tests:\n")
                    for fail_msg in res['failed_tests']:
                        f.write(f"    {fail_msg}\n")
                
                if res.get('safety_violations', 0) > 0:
                    f.write(f"  Safety violations: {res['safety_violations']}\n")
                
                if res.get('timeout_violations', 0) > 0:
                    f.write(f"  Timeout violations: {res['timeout_violations']}\n")
            
            if total_score is None or max_score is None:
                f.write("Total Score: Time limit exceeded or error\n")
            else:
                f.write(f"Total Score: {total_score:.2f}/{max_score}\n")
    
    def _record_student_grade(self, userid: str, total_score: float, max_score: float) -> None:
        """Record student's grade in session state."""
        self.user_grades[userid] = total_score if max_score else 0 if max_score else None
        self.user_grades_percentage[userid] = (total_score / max_score * 100 
                                             if max_score else 0 if max_score else None)
    
    def _add_test_results_to_csv(self, userid: str, test_keys: List[str], 
                                test_results: Dict, passfail_rows: List, msg_rows: List) -> None:
        """Add test results to CSV row data."""
        pf_row = [userid]
        msg_row = [userid]
        
        for key in test_keys:
            pf_row.append(test_results[key][0])
            msg_row.append(test_results[key][1])
        
        passfail_rows.append(pf_row)
        msg_rows.append(msg_row)
    
    def _collect_summary_statistics(self, userid: str, results: List[Dict]) -> None:
        """Collect summary statistics for the grading session."""
        import re
        
        for i, res in enumerate(results):
            percent = res['passed'] / res['total'] if res['total'] else 0
            self.summary_scores[i].append(percent)
            self.safety_violations[i] += res.get('safety_violations', 0)
            self.timeout_violations[i] += res.get('timeout_violations', 0)
            
            if res.get('safety_violations', 0) > 0:
                self.safety_violation_details.append(f"User: {userid}, Cell: {res['cell_index']}")
            
            if res.get('timeout_violations', 0) > 0:
                self.timeout_violation_details.append(f"User: {userid}, Cell: {res['cell_index']}")
            
            for fail_msg in res.get('failed_tests', []):
                if 'error (' in fail_msg:
                    m = re.search(r'error \(([^)]+)\)', fail_msg)
                    err_type = m.group(1) if m else 'UnknownError'
                    self.exec_err_details.append(f"User: {userid}, Cell: {res['cell_index']}, Error: {err_type}")
                    self.exec_err_counts[err_type] += 1
                
                if 'failed' in fail_msg.lower():
                    self.wa_lines.append(f"User: {userid}, Cell: {res['cell_index']}, Message: {fail_msg}")
    
    def _write_test_results(self, test_keys: List[str], passfail_rows: List, msg_rows: List) -> None:
        """Write pass/fail and message CSV files."""
        summary_dir = self.config.get_homework_dir()
        
        # Handle existing files
        pf_path = os.path.join(summary_dir, "test_passfail.csv")
        msg_path = os.path.join(summary_dir, "test_failmsg.csv")
        
        if os.path.exists(pf_path):
            os.rename(pf_path, os.path.join(summary_dir, "test_passfail_bkup.csv"))
        if os.path.exists(msg_path):
            os.rename(msg_path, os.path.join(summary_dir, "test_failmsg_bkup.csv"))
        
        # Write new files
        pf_header = ["ID"] + test_keys
        msg_header = ["ID"] + test_keys
        
        with open(pf_path, "w", newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(pf_header)
            writer.writerows(passfail_rows)
        
        with open(msg_path, "w", newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(msg_header)
            writer.writerows(msg_rows)
    
    def _write_wrong_answers(self) -> None:
        """Write wrong answers to wa.txt file."""
        if self.wa_lines:
            wa_path = os.path.join(self.config.get_homework_dir(), "wa.txt")
            with open(wa_path, "w", encoding="utf-8") as f:
                for line in self.wa_lines:
                    f.write(line + "\n")
    
    def _write_summary_metadata(self) -> None:
        """Write grading summary metadata."""
        meta_path = os.path.join(self.config.get_homework_dir(), "grading_summary.txt")
        
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write("Problem Index,Avg Percentage,Safety Violations,Timeout Violations\n")
            
            for i in sorted(self.summary_scores.keys()):
                avg_pct = (sum(self.summary_scores[i]) / len(self.summary_scores[i]) 
                          if self.summary_scores[i] else 0)
                f.write(f"{i},{avg_pct:.2%},{self.safety_violations[i]},{self.timeout_violations[i]}\n")
            
            self._write_violation_details(f)
            self._write_error_details(f)
            self._write_problem_notebooks(f)
            self._write_average_score(f)
    
    def _write_violation_details(self, f) -> None:
        """Write safety and timeout violation details."""
        if self.safety_violation_details:
            f.write("\nSafety Violations (User, Cell):\n")
            for detail in self.safety_violation_details:
                f.write(f"{detail}\n")
        
        if self.timeout_violation_details:
            f.write("\nTimeout Violations (User, Cell):\n")
            for detail in self.timeout_violation_details:
                f.write(f"{detail}\n")
    
    def _write_error_details(self, f) -> None:
        """Write execution error details."""
        if self.exec_err_details:
            f.write("\nExecution Errors (User, Cell, Error Type):\n")
            for detail in self.exec_err_details:
                f.write(f"{detail}\n")
            
            f.write("\nExecution Error Counts by Type:\n")
            for err_type, count in self.exec_err_counts.items():
                f.write(f"{err_type}: {count}\n")
    
    def _write_problem_notebooks(self, f) -> None:
        """Write details about problematic notebooks."""
        if self.unreadable_notebooks:
            f.write("\nUnreadable Notebooks (User IDs):\n")
            for uid in self.unreadable_notebooks:
                f.write(f"{uid}\n")
        
        if self.cell_mismatch_users:
            f.write("\nCell Count Mismatch (User, Expected, Got):\n")
            for detail in self.cell_mismatch_users:
                f.write(f"{detail}\n")
    
    def _write_average_score(self, f) -> None:
        """Write average total score."""
        valid_scores = [score for score in self.user_grades.values() if score is not None]
        if valid_scores:
            avg_total_score = sum(valid_scores) / len(valid_scores)
            _, _, max_score, _ = self.notebook_grader.grade_notebook()
            if max_score is not None:
                f.write(f"\nAverage Total Score: {avg_total_score:.2f}/{max_score}\n")
    
    def _update_gradebook(self, userids_done: List[str]) -> None:
        """Update the main gradebook with grades."""
        gradebook_path = self.config.get_gradebook_path()
        homework_title = self.config.get_homework_title()
        
        # Read current gradebook
        with open(gradebook_path, newline='', encoding='utf-8') as f:
            rows = list(csv.reader(f))
        
        header = rows[0]
        
        # Find points possible row
        points_row_idx = None
        for idx, row in enumerate(rows):
            if any("Points Possible" in cell for cell in row):
                points_row_idx = idx
                break
        
        # Get max score
        _, _, max_score, _ = self.notebook_grader.grade_notebook()
        
        # Find or create homework column
        col_idx = self._find_or_create_homework_column(header, rows, homework_title, 
                                                      max_score, points_row_idx)
        
        # Update grades
        self._update_grade_column(rows, header, col_idx)
        
        # Write filtered output
        self._write_filtered_gradebook(header, rows, col_idx)
    
    def _find_or_create_homework_column(self, header: List[str], rows: List[List[str]], 
                                       homework_title: str, max_score: float, 
                                       points_row_idx: Optional[int]) -> int:
        """Find existing homework column or create a new one."""
        col_idx = None
        for i, col in enumerate(header):
            if col.startswith(homework_title):
                col_idx = i
                break
        
        if col_idx is None:
            # Create new column
            header.append(homework_title)
            col_idx = len(header) - 1
            
            if points_row_idx is not None:
                rows[points_row_idx].append(str(max_score))
            
            for r in rows[1:]:
                r.append("")
        
        return col_idx
    
    def _update_grade_column(self, rows: List[List[str]], header: List[str], col_idx: int) -> None:
        """Update the grades in the specified column."""
        for row in rows[1:]:
            if len(row) < len(header):
                row += [""] * (len(header) - len(row))
            
            id_val = row[header.index("ID")].strip() if "ID" in header else ""
            if id_val in self.user_grades:
                row[col_idx] = f"{self.user_grades[id_val]:.2f}"
    
    def _write_filtered_gradebook(self, header: List[str], rows: List[List[str]], grade_col_idx: int) -> None:
        """Write the filtered gradebook output."""
        # Define required columns
        HEADERS = ["Student", "ID", "SIS Login ID", "Section"]
        ID_indices = [header.index(h) for h in HEADERS if h in header]
        
        # Build output column indices
        output_indices = ID_indices.copy()
        if grade_col_idx not in output_indices:
            output_indices.append(grade_col_idx)
        
        # Filter and write rows
        filtered_rows = []
        for row in [header] + rows[1:]:
            if len(row) < len(header):
                row += [""] * (len(header) - len(row))
            filtered_rows.append([row[i] for i in output_indices])
        
        out_path = os.path.join(os.path.dirname(__file__), "grade_updated.csv")
        with open(out_path, "w", newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(filtered_rows)


def main():
    """Main entry point for the grading system."""
    session = GradingSession()
    session.grade_all_students()


if __name__ == "__main__":
    main()