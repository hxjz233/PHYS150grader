
import csv
import os
import nbformat
import importlib.util
from collections import defaultdict
import toml

# Dynamically import gradecell.py
spec = importlib.util.spec_from_file_location("gradecell", os.path.join(os.path.dirname(__file__), "gradecell.py"))
gradecell = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gradecell)

# Read config
config = toml.load(os.path.join(os.path.dirname(__file__), "config.toml"))
HOMEWORK_DIR = config.get("homework_dir", None)
SUBMISSIONS_DIR = os.path.join(HOMEWORK_DIR, config.get("submissions_dir", "submissions"))

GRADEBOOK = config.get("gradebook", "grade.csv")
SUMMARY_DIR = HOMEWORK_DIR
FEEDBACK_DIR = os.path.join(HOMEWORK_DIR, config.get("feedback_dir", "feedback"))

# Explicitly define the first 4 column headers
HEADERS = ["Student", "ID", "SIS Login ID", "Section"]

def get_userids_from_csv(csv_path):
	userids = []
	with open(csv_path, newline='', encoding='utf-8') as f:
		reader = csv.DictReader(f)
		for row in reader:
			id_val = row.get("ID")
			if id_val and id_val.strip():
				userids.append(id_val.strip())
	return userids

def grade_notebook_for_user(userid):
	nb_path = os.path.join(SUBMISSIONS_DIR, f"{userid}.ipynb")
	print(f"Grading notebook for user {userid} at {nb_path}")
	if not os.path.exists(nb_path):
		return None, None, None
	nb = nbformat.read(open(nb_path, encoding="utf-8"), as_version=4)
	results, total_score, max_score = gradecell.grade_notebook(nb)
	return results, total_score, max_score

def write_user_grade_txt(userid, results, total_score, max_score):
	txt_path = os.path.join(FEEDBACK_DIR, f"{userid}.txt")
	os.makedirs(FEEDBACK_DIR, exist_ok=True)
	with open(txt_path, "w", encoding="utf-8") as f:
		for res in results:
			f.write(f"Cell {res['cell_index']}: {res['passed']}/{res['total']} tests passed, Score: {res['score']:.2f}/{res['pts']}\n")
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

def main():
	userids = get_userids_from_csv(GRADEBOOK)
	summary_scores = defaultdict(list)
	safety_violations = defaultdict(int)
	timeout_violations = defaultdict(int)
	safety_violation_details = []
	timeout_violation_details = []
	exec_err_details = []
	exec_err_counts = defaultdict(int)
	user_grades = {}
	user_grades_percentage = {}
	unreadable_notebooks = []
	wa_lines = []
	for userid in userids:
		try:
			results, total_score, max_score = grade_notebook_for_user(userid)
		except Exception:
			results, total_score, max_score = None, None, None
		if results is None:
			unreadable_notebooks.append(userid)
			continue
		write_user_grade_txt(userid, results, total_score, max_score)
		user_grades[userid] = total_score if max_score else 0 if max_score else None
		user_grades_percentage[userid] = total_score / max_score * 100 if max_score else 0 if max_score else None
		for i, res in enumerate(results):
			percent = res['passed'] / res['total'] if res['total'] else 0
			summary_scores[i].append(percent)
			safety_violations[i] += res.get('safety_violations', 0)
			timeout_violations[i] += res.get('timeout_violations', 0)
			if res.get('safety_violations', 0) > 0:
				safety_violation_details.append(f"User: {userid}, Cell: {res['cell_index']}")
			if res.get('timeout_violations', 0) > 0:
				timeout_violation_details.append(f"User: {userid}, Cell: {res['cell_index']}")
			# Record exec errors from failed_tests
			for fail_msg in res.get('failed_tests', []):
				if 'error (' in fail_msg:
					# Example: 'Test 1 error (TypeError) on input (x=1): ...'
					import re
					m = re.search(r'error \(([^)]+)\)', fail_msg)
					err_type = m.group(1) if m else 'UnknownError'
					exec_err_details.append(f"User: {userid}, Cell: {res['cell_index']}, Error: {err_type}")
					exec_err_counts[err_type] += 1
				# Write assertion errors (wrong answers) to wa.txt
				if 'failed' in fail_msg.lower():
					wa_lines.append(f"User: {userid}, Cell: {res['cell_index']}, Message: {fail_msg}")

	# Write all assertion errors to wa.txt
	if wa_lines:
		wa_path = os.path.join(SUMMARY_DIR, "wa.txt")
		with open(wa_path, "w", encoding="utf-8") as waf:
			for line in wa_lines:
				waf.write(line + "\n")

	# Write summary metadata
	meta_path = os.path.join(SUMMARY_DIR, "grading_summary.txt")
	with open(meta_path, "w", encoding="utf-8") as f:
		f.write("Problem Index,Avg Percentage,Safety Violations,Timeout Violations\n")
		for i in sorted(summary_scores.keys()):
			avg_pct = sum(summary_scores[i]) / len(summary_scores[i]) if summary_scores[i] else 0
			f.write(f"{i},{avg_pct:.2%},{safety_violations[i]},{timeout_violations[i]}\n")
		if safety_violation_details:
			f.write("\nSafety Violations (User, Cell):\n")
			for detail in safety_violation_details:
				f.write(f"{detail}\n")
		if timeout_violation_details:
			f.write("\nTimeout Violations (User, Cell):\n")
			for detail in timeout_violation_details:
				f.write(f"{detail}\n")
		if exec_err_details:
			f.write("\nExecution Errors (User, Cell, Error Type):\n")
			for detail in exec_err_details:
				f.write(f"{detail}\n")
			f.write("\nExecution Error Counts by Type:\n")
			for err_type, count in exec_err_counts.items():
				f.write(f"{err_type}: {count}\n")
		if unreadable_notebooks:
			f.write("\nUnreadable Notebooks (User IDs):\n")
			for uid in unreadable_notebooks:
				f.write(f"{uid}\n")

	# Add grade column to gradebook with config.toml homework_title
	homework_title = config.get("homework_title", "New Assignment")
	with open(GRADEBOOK, newline='', encoding='utf-8') as f:
		rows = list(csv.reader(f))
	header = rows[0]
	# Find points possible row (usually 2nd row)
	points_row_idx = None
	for idx, row in enumerate(rows):
		if any("Points Possible" in cell for cell in row):
			points_row_idx = idx
			break
	# Get max_score from gradecell
	_, _, max_score = gradecell.grade_notebook()
	# Find column index matching homework_title prefix
	col_idx = None
	for i, col in enumerate(header):
		if col.startswith(homework_title):
			col_idx = i
			break
	if col_idx is None:
		# No matching column, append new
		header.append(homework_title)
		col_idx = len(header) - 1
		if points_row_idx is not None:
			rows[points_row_idx].append(str(max_score))
		for r in rows[1:]:
			r.append("")
	for row in rows[1:]:
		if len(row) < len(header):
			row += [""] * (len(header) - len(row))
		id_val = row[header.index("ID")].strip() if "ID" in header else ""
		if id_val in user_grades:
			row[col_idx] = f"{user_grades[id_val]:.2f}"
	# Find their indices in the header row
	ID_indices = [header.index(h) for h in HEADERS]
	grade_col_idx = col_idx
	# Avoid duplicate if grade_col_idx is within first 4
	output_indices = ID_indices.copy()
	if grade_col_idx not in output_indices:
		output_indices.append(grade_col_idx)
	# Prepare filtered rows
	filtered_rows = []
	for row in [header] + rows[1:]:
		# Pad row if needed
		if len(row) < len(header):
			row += [""] * (len(header) - len(row))
		filtered_rows.append([row[i] for i in output_indices])
	# Define output path before writing
	out_path = os.path.join(os.path.dirname(__file__), "grade_updated.csv")
	with open(out_path, "w", newline='', encoding='utf-8') as f:
		writer = csv.writer(f)
		writer.writerows(filtered_rows)

if __name__ == "__main__":
	main()