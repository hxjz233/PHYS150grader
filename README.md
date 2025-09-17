# PHYS150 Homework Grader

This is a Grading system for TAMU PHYS150 developed by GPT-4.1 and Zhuowei Zhang.

## Inputs for grading
1. `submissions.zip` downloaded from Canvas
2. gradebook downloaded from Canvas
3. Tests written for the homework as `tester.toml`

## Configuration
The configuration takes place in two places:

In `config.toml`, 
- `homework_dir` for the folder name that you want to put the `submissions.zip` in. This will be the folder you put all grading summary and feedback info in for the current problem set. It is recommended that each problem set be graded in a different directory 
- `submissions_dir` for the folder name "`homework_dir/submissions_dir`", into which `submissions.zip` shall preprocess (extract and rename) the homework files.
- `feedback_dir` for the folder name "`homework_dir/feedback_dir`", into which grading details are put in (and later on submitted to student assignment comments)
- `course_number` for the course id that appears in the canvas url
- `homework_title` for the current assignment name, i.e. the gradebook header for the updated gradebook
- `gradebook` for the file name of the gradebook downloaded from canvas. This allows the grading system to enumerate the student IDs and grade.
- - It is recommended that you export from Canvas everytime before you grade, as there may constantly be student dropping the class and changing the student name list that you should grade
- `timeout` for the timeout limit in each cell execution (in secs).
- `debug` true for suppressing real submission of feedbacks
- `headless` true for hiding the Chrome Explorer that automatically submits feedback

In `tester.toml`, which contains tests for each problem set and should be placed under the corresponding `homework_dir`,
- `next_code_cell` for the next code cell that contains student's solution. e.g. for a hw in format
> `Markdown`
> `Markdown`
> `Code` (initialization of variables as indicated by problem)
> `Code` (student solution)
> `Markdown`
> `Code` (initialization of variables as indicated by problem)
> `Code` (student solution)

You should put `next_code_cell=2` for prob 1 and `next_code_cell=2` for prob 2. The system then knows to read the 2nd and 4th `Code` block with testing variables. This way of denoting solution cell numbers in `tester.toml` enables a more flexible way to stack the problems and is expected to give extra flexibility when moving the problems around in their order/across different assignments.
- `pts` points assigned to this problem. The student would get passed proportion of points out of all tests for that problem
- `line_offset` for the number of ignored lines within cell when reading student solution. This is useful when the lines for the initialization of problem variables are written with student solution within the same cell. There you would want to skip reassigning variables to default nubmers and read only from the lines where the student solution is at.
- `tests` for the tests. `type` accepts `variable` or `output` for distinguishing whether the system should look at specific variable or at the standard output. `variables` for the testing variables. `expected` contains the expected result.

## To use:
1. export gradebook from Canvas and placed it at the root of this grading system
2. get `submissions.zip` for the batch of student homework and place it under the `homework_dir` you configured.
3. run `preprocess.py` and expect the homework files be extracted and renamed into `homework_dir/submissions_dir`
4. run `grader.py` and expect
    1. feedback in `homework_dir/feedback_dir` which contains grading details for each students
    2. `grading_summary.txt` which contains problem numbers, avg. acc., and info about exceptions thrown for student codes.
    3. the creation of `grade_updated.csv` at the root, which updates/appends a column according to `homework_title`
5. After examining your grading outcomes, run `feedback.py` and login with duo. 

## All outputs, to sum up
1. updated gradebook
2. grading summary of current assignment
3. feedback folder for grading details, and should be received as comments of the corresponding homework in the student's view

## Misc
`safecode.py` is designed to primitively protects the grader from OS operations and deadloop attacks from students when `grader.py` is running. 
However, the behavior differs depending on the OS the code is operated in. 
The grading code can be run on both windows and unix,
but running in Windows will not have timeout limits activated and therefore makes the grader unprotected from deadloops.
If a deadloop occurs in a students code, you will have to exclude it manually.
Running in unix environment allows a cell to run up to `timeout` secs.

## TODO
- allow manual operation for grading
- approximated output