import json
import sqlite3
import requests
from datetime import datetime

# Load configuration from JSON file
with open('unit_test_config.json') as config_file:
    config = json.load(config_file)

# Extract configuration details
db_path = config['db_path']
api_token = config['api_token']
project_code = config['project_code']
qase_base_url = config['qase_base_url']
suite_id = config['suite_id']
run_name = config.get('run_name', 'Test Run')

# Add current date and time to the run name
current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
run_name_with_date = f"{run_name}_{current_datetime}"

# Connect to SQLite database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Function to create a test run
def create_test_run(project_code, api_token, suite_id, run_name, test_cases):
    url = f"{qase_base_url}/run/{project_code}"
    headers = {"Content-Type": "application/json", "Token": api_token}
    payload = {
        "title": run_name,
        "suite_id": suite_id,
        "cases": test_cases  # Ensure this is a list of integers
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json().get('result', {})
        return result.get('id')
    except requests.RequestException as e:
        print(f"Failed to create test run: {e}")
        return None

# Function to fetch the previous log for a specific test case in a test run
def fetch_previous_logs(project_code, api_token, run_id, case_id):
    url = f"{qase_base_url}/result/{project_code}/{run_id}/cases/{case_id}"
    headers = {"Token": api_token}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        result = response.json().get('result', {})
        return result.get('comment', '')  # Fetch previous comment/log
    except requests.RequestException as e:
        print(f"Failed to fetch previous logs: {e}")
        return ""

# Function to update the test run with results and logs
def update_test_run(project_code, api_token, run_id, case_id, status, detailed_comment):
    url = f"{qase_base_url}/result/{project_code}/{run_id}"
    headers = {"Content-Type": "application/json", "Token": api_token}
    payload = {
        "case_id": case_id,
        "status": status,
        "comment": detailed_comment  # Include detailed logs
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"Failed to update test case ID {case_id}: {e}")
        return False

def complete_test_run(project_code, api_token, run_id):
    url = f"{qase_base_url}/run/{project_code}/{run_id}/complete"
    headers = {"Content-Type": "application/json", "Token": api_token}
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"Failed to complete test run ID {run_id}: {e}")
        return False

# Function to fetch existing test cases from Qase with pagination
def fetch_test_cases(project_code, api_token, suite_id):
    test_cases = {}
    offset = 0
    limit = 100  

    while True:
        url = f"{qase_base_url}/case/{project_code}?suite_id={suite_id}&limit={limit}&offset={offset}"
        headers = {"Token": api_token}
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            result = response.json().get('result', {})
            cases = result.get('entities', [])
            if not cases:
                break

            for case in cases:
                # Store test cases with unique titles to their IDs
                test_cases[case['id']] = case['title'].strip().lower()

            offset += limit
        except requests.RequestException as e:
            print(f"Failed to fetch test cases: {e}")
            break

    return test_cases

# Fetch data from the database
cursor.execute('SELECT test_name, status, details, duration FROM unit_test_results')
rows = cursor.fetchall()

# Fetch all existing test cases
test_case_mapping = fetch_test_cases(project_code, api_token, suite_id)

# Create a test case list for the new test run, including all test cases
test_cases = list(test_case_mapping.keys())  # List of integer IDs

# Create a new test run with all the test cases
run_id = create_test_run(project_code, api_token, suite_id, run_name_with_date, test_cases)
if not run_id:
    print("Failed to create a test run. Exiting.")
    conn.close()
    exit()

print(f"New test run created with ID: {run_id}")

# Map SQLite statuses to Qase statuses
status_mapping = {
    "passed": "passed",
    "failed": "failed",
    "skipped": "skipped"
}

# Track overall update success
update_success = True

# Process each row from the SQLite database
for row in rows:
    test_name = row[0].strip().lower()
    status = row[1].strip().lower()
    details = row[2].strip()
    duration = row[3] if row[3] else 'N/A'
    qase_status = status_mapping.get(status, "skipped")

    # Find all test case IDs with the same name
    matching_case_ids = [case_id for case_id, title in test_case_mapping.items() if title == test_name]

    if matching_case_ids:
        for case_id in matching_case_ids:
            # Fetch the previous logs for this test case in the test run
            previous_logs = fetch_previous_logs(project_code, api_token, run_id, case_id)

            # Create a detailed log with current run information and previous logs
            detailed_comment = (
                f"Current Run:\n"
                f"Status: {qase_status}\n"
                f"Details: {details}\n"
                f"Duration: {duration}\n"
                f"---\n"
                f"Previous Logs:\n"
                f"{previous_logs}"
            )

            # Update the test run with the result and combined logs
            if not update_test_run(project_code, api_token, run_id, case_id, qase_status, detailed_comment):
                update_success = False
    else:
        print(f"Test case '{test_name}' does not exist. Skipping...")

if update_success:
    print("Update status successfully.")
else:
    print("Some updates failed.")

# Close the SQLite connection
conn.close()

