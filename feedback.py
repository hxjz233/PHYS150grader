"""
Canvas feedback upload system using the new modular architecture.
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import os
import sys
from getpass import getpass
import csv
import re

# Add the core module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))

from core.config import ConfigManager


class CanvasFeedbackUploader:
    """Handles uploading feedback to Canvas using Selenium."""
    
    def __init__(self, config_manager: ConfigManager = None):
        self.config = config_manager or ConfigManager()
        self.username = os.getenv("CANVAS_USERNAME") or input("Enter Canvas username: ")
        self.password = os.getenv("CANVAS_PASSWORD") or getpass("Enter Canvas password: ")
        
        # Get Canvas-specific configuration
        self.course_number = self.config.config.get("course_number")
        self.homework_title = self.config.get_homework_title()
        self.gradebook_path = self.config.get_gradebook_path()
        self.feedback_dir = self.config.get_feedback_dir()
        self.debug_mode = self.config.config.get("debug", False)
        self.headless_mode = self.config.config.get("headless", False)
        
        # Extract assignment ID from gradebook
        self.assignment_id = self._extract_assignment_id()
        
        # Determine Chrome user data directory
        if os.name == "nt":
            self.user_data_dir = os.path.expanduser("~/AppData/Local/Google/Chrome/User Data")
        else:
            self.user_data_dir = os.path.expanduser("~/.config/google-chrome")
    
    def _extract_assignment_id(self) -> str:
        """Extract assignment ID from gradebook header."""
        with open(self.gradebook_path, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
        
        for col in header:
            m = re.match(rf"{re.escape(self.homework_title)} \((\d+)\)", col)
            if m:
                return m.group(1)
        
        raise ValueError(f"Assignment ID not found for title '{self.homework_title}' in gradebook header.")
    
    def _setup_driver(self) -> webdriver.Chrome:
        """Set up Chrome driver with appropriate options."""
        chrome_options = Options()
        if self.headless_mode:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--remote-debugging-port=9222")
        
        return webdriver.Chrome(options=chrome_options)
    
    def _login_to_canvas(self, driver: webdriver.Chrome) -> webdriver.Chrome:
        """Login to Canvas through Microsoft authentication."""
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "i0116"))
        )
        
        # Enter username
        username = driver.find_element(By.ID, "i0116")
        username.send_keys(self.username)
        
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "idSIButton9"))
        )
        next_bot = driver.find_element(By.ID, "idSIButton9")
        next_bot.click()
        
        # Enter password
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "idA_PWD_ForgotPassword"))
        )
        pwd = driver.find_element(By.ID, "i0118")
        pwd.send_keys(self.password)
        next_bot = driver.find_element(By.ID, "idSIButton9")
        next_bot.click()
        
        # Trust browser
        WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.ID, "trust-browser-button"))
        )
        next_bot = driver.find_element(By.ID, "trust-browser-button")
        next_bot.click()
        
        # Stay signed in
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "KmsiCheckboxField"))
        )
        next_bot = driver.find_element(By.ID, "idSIButton9")
        next_bot.click()
        
        return driver
    
    def _upload_feedback(self, driver: webdriver.Chrome, feedback_path: str) -> None:
        """Upload feedback text to Canvas."""
        # Read feedback text from file
        with open(feedback_path, "r", encoding="utf-8") as f:
            feedback_text = f.read()
        
        # Wait for student select menu to appear (indicates page is fully loaded)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.ui-selectmenu-menu[style*='z-index: 101'] ul#students_selectmenu-menu"))
        )
        
        # Wait for iframe and switch to it
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[id*='rce_textarea']"))
        )
        iframe = driver.find_element(By.CSS_SELECTOR, "iframe[id*='rce_textarea']")
        driver.switch_to.frame(iframe)
        
        # Wait for contenteditable body and enter feedback
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body.mce-content-body[contenteditable='true']"))
        )
        editor_body = driver.find_element(By.CSS_SELECTOR, "body.mce-content-body[contenteditable='true']")
        driver.execute_script("arguments[0].focus();", editor_body)
        
        # Send feedback text, preserving formatting and handling tabs
        for line in feedback_text.splitlines():
            # Replace tabs with spaces to prevent focus issues
            safe_line = line.replace('\t', '    ')
            editor_body.send_keys(safe_line)
            editor_body.send_keys("\n")
        
        # Switch back to main content
        driver.switch_to.default_content()
        
        # Submit feedback
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "comment_submit_button"))
        )
        submit = driver.find_element(By.ID, "comment_submit_button")
        
        if not self.debug_mode:
            driver.execute_script("arguments[0].click();", submit)
            print(f'Submitted {feedback_path}.')
        else:
            print(f'DEBUG MODE: Would have submitted {feedback_path}.')
        
        WebDriverWait(driver, 1)
    
    def upload_all_feedback(self, start_id: str = None) -> None:
        """Upload feedback for all students.
        
        Args:
            start_id: Optional student ID to start from. If provided, only uploads
                     feedback for students with IDs >= start_id.
        """
        driver = self._setup_driver()
        
        try:
            # Get sorted list of feedback files
            feedback_files = sorted([f for f in os.listdir(self.feedback_dir) if f.endswith('.txt')])
            
            if not feedback_files:
                print(f"No .txt files found in {self.feedback_dir}")
                return
                
            # If start_id is provided, find where to start in the sorted list
            if start_id:
                # Find the index where we should start
                start_index = 0
                for i, fname in enumerate(feedback_files):
                    current_id = os.path.splitext(fname)[0]
                    if current_id >= start_id:
                        start_index = i
                        break
                feedback_files = feedback_files[start_index:]
                if not feedback_files:
                    print(f"No feedback files found with ID >= {start_id}")
                    return
                    
                print(f"Starting uploads from student ID: {os.path.splitext(feedback_files[0])[0]}")
            
            # Login with first student
            first_file = feedback_files[0]
            first_student_id = os.path.splitext(first_file)[0]
            login_url = (f"https://canvas.tamu.edu/courses/{self.course_number}/gradebook/"
                        f"speed_grader?assignment_id={self.assignment_id}&student_id={first_student_id}")
            
            print(f"Navigating to initial page for login: {login_url}")
            driver.get(login_url)
            driver = self._login_to_canvas(driver)
            
            # Upload feedback for first student
            print(f"Uploading feedback for first student: {first_student_id}")
            first_feedback_path = os.path.join(self.feedback_dir, first_file)
            self._upload_feedback(driver, first_feedback_path)
            
            # Process remaining students
            for fname in feedback_files[1:]:
                student_id = os.path.splitext(fname)[0]
                feedback_path = os.path.join(self.feedback_dir, fname)
                canvas_url = (f"https://canvas.tamu.edu/courses/{self.course_number}/gradebook/"
                             f"speed_grader?assignment_id={self.assignment_id}&student_id={student_id}")
                
                print(f"Navigating to {canvas_url}")
                driver.get(canvas_url)
                self._upload_feedback(driver, feedback_path)
        
        finally:
            driver.quit()


def main():
    """Main entry point for feedback upload."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Upload feedback to Canvas")
    parser.add_argument("--start-id", type=str, help="Start uploading from this student ID")
    args = parser.parse_args()
    
    uploader = CanvasFeedbackUploader()
    uploader.upload_all_feedback(start_id=args.start_id)


if __name__ == "__main__":
    main()