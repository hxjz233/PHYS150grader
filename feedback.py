from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import os
from getpass import getpass
import csv
import toml

my_username = os.getenv("CANVAS_USERNAME") or input("Enter Canvas username: ")
my_password = os.getenv("CANVAS_PASSWORD") or getpass("Enter Canvas password: ")

# Read config
config = toml.load(os.path.join(os.path.dirname(__file__), "config.toml"))
course_number = config.get("course_number")
homework_title = config.get("homework_title")
gradebook_path = config.get("gradebook")
feedback_dir = os.path.join(config.get("homework_dir"), config.get("feedback_dir"))
debug_mode = config.get("debug", False)
headless_mode = config.get("headless", False)

# Extract assignment_id from gradebook header
with open(gradebook_path, newline='', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)
assignment_id = None
import re
for col in header:
    m = re.match(rf"{re.escape(homework_title)} \((\d+)\)", col)
    if m:
        assignment_id = m.group(1)
        break
if not assignment_id:
    raise ValueError(f"Assignment ID not found for title '{homework_title}' in gradebook header.")

# if os.name == "nt":
#     user_data_dir = "C:/Users/hxjz233/AppData/Local/Google/Chrome/User Data"  # e.g., "C:/Users/YourName/AppData/Local/Google/Chrome/User Data"
# else:
#     user_data_dir = os.path.expanduser("/mnt/c/Users/hxjz233/AppData/Local/Google/Chrome/User Data")
if os.name == "nt":
    user_data_dir = os.path.expanduser("~/AppData/Local/Google/Chrome/User Data")
else:
    user_data_dir = os.path.expanduser("~/.config/google-chrome")


def login_to_canvas(driver):
    # The driver will be navigated to the correct URL for each student later
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "i0116"))
    )
    username = driver.find_element(By.ID, "i0116")
    username.send_keys(my_username)
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.ID, "idSIButton9"))
    )
    next_bot = driver.find_element(By.ID, "idSIButton9")
    next_bot.click()
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "idA_PWD_ForgotPassword"))
    )
    pwd = driver.find_element(By.ID, "i0118")
    pwd.send_keys(my_password)
    next_bot = driver.find_element(By.ID, "idSIButton9")
    next_bot.click()
    WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.ID, "trust-browser-button"))
    )
    next_bot = driver.find_element(By.ID, "trust-browser-button")
    next_bot.click()
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "KmsiCheckboxField"))
    )
    next_bot = driver.find_element(By.ID, "idSIButton9")
    next_bot.click()
    return driver

def upload_feedback(driver, feedback_path):
    # Read feedback text from file
    with open(feedback_path, "r", encoding="utf-8") as f:
        feedback_text = f.read()
        
    # Wait for student select menu to appear before continuing. This is the true indicator that the page has fully loaded.
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.ui-selectmenu-menu[style*='z-index: 101'] ul#students_selectmenu-menu"))
    )

    # Wait for iframe to be present and switch to it
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[id*='rce_textarea']"))
    )
    iframe = driver.find_element(By.CSS_SELECTOR, "iframe[id*='rce_textarea']")
    driver.switch_to.frame(iframe)

    # Wait for the contenteditable body to be present
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "body.mce-content-body[contenteditable='true']"))
    )
    editor_body = driver.find_element(By.CSS_SELECTOR, "body.mce-content-body[contenteditable='true']")
    driver.execute_script("arguments[0].focus();", editor_body)
    # Send feedback text, preserving formatting
    for line in feedback_text.splitlines():
        editor_body.send_keys(line)
        editor_body.send_keys("\n")

    # Switch back to main content before submitting
    driver.switch_to.default_content()
    # Wait for submit button to be present
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "comment_submit_button"))
    )
    submit = driver.find_element(By.ID, "comment_submit_button")
    
    if not debug_mode:
        driver.execute_script("arguments[0].click();", submit)
        print(f'Submitted {feedback_path}.')
    else:
        print(f'DEBUG MODE: Would have submitted {feedback_path}.')

    WebDriverWait(driver, 1)


if __name__ == "__main__":
    chrome_options = Options()
    if headless_mode:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--remote-debugging-port=9222")

    driver = webdriver.Chrome(options=chrome_options)
    for fname in os.listdir(feedback_dir):
        if not fname.endswith('.txt'):
            continue
        student_id = os.path.splitext(fname)[0]
        feedback_path = os.path.join(feedback_dir, fname)
        canvas_url = f"https://canvas.tamu.edu/courses/{course_number}/gradebook/speed_grader?assignment_id={assignment_id}&student_id={student_id}"
        print(f"Navigating to {canvas_url}")
        driver.get(canvas_url)
        # Login only once, on first student
        if fname == sorted(os.listdir(feedback_dir))[0]:
            driver = login_to_canvas(driver)
        upload_feedback(driver, feedback_path)
    driver.quit()  # Close browser when done
