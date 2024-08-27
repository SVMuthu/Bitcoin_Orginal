import json
import os
import sqlite3
import requests
from datetime import datetime

# Load configuration from JSON file
with open('/home/svm/Downloads/Bitcoin_Orginal/Output_log/unit_test_config.json') as config_file:
    config = json.load(config_file)

# Load configuration from JSON file
with open('unit_test_config.json') as config_file:
    config = json.load(config_file)

# Extract configuration details
db_path = config['db_path']
api_token = config['api_token']
project_code = config['project_code']
qase_base_url = config['qase_base_url']
suite_id = config['suite_id']
run_name = config.get('run_name', 'Unit Test Run')
log_dir = config.get('log_dir')  # Directory to store logs

# Ensure the log directory exists
os.makedirs(log_dir, exist_ok=True)

# Connect to SQLite database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Function to create a test run
def create_test_run(project_code, api_token, suite_id, run_name):
    url = f"{qase_base_url}/run/{project_code}"
    headers = {"Content-Type": "application/json", "Token": api_token}
    payload = {
        "title": run_name,
        "suite_id": suite_id,
        "cases": []
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json().get('result', {}).get('id')
    else:
        print(f"Failed to create test run: {response.status_code}, {response.text}")
        return None

# Function to create a new test case in Qase
def create_test_case(project_code, api_token, suite_id, test_name):
    url = f"{qase_base_url}/case/{project_code}"
    headers = {"Content-Type": "application/json", "Token": api_token}
    payload = {
        "title": test_name,
        "suite_id": suite_id
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json().get('result', {}).get('id')
    else:
        print(f"Failed to create test case '{test_name}': {response.status_code}, {response.text}")
        return None

# Function to update the test run with results, including detailed logs in comments
def update_test_run(project_code, api_token, run_id, case_id, status, comment):
    url = f"{qase_base_url}/result/{project_code}/{run_id}"
    headers = {"Content-Type": "application/json", "Token": api_token}
    payload = {
        "case_id": case_id,
        "status": status,
        "comment": comment
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return True
    else:
        print(f"Failed to update test case: {response.status_code}, {response.text}")
        return False

# Function to complete the test run
def complete_test_run(project_code, api_token, run_id):
    url = f"{qase_base_url}/run/{project_code}/{run_id}/complete"
    headers = {"Content-Type": "application/json", "Token": api_token}
    response = requests.post(url, headers=headers)
    return response.status_code == 200

# Function to fetch existing test cases from Qase with pagination
def fetch_test_cases(project_code, api_token, suite_id):
    test_cases = {}
    offset = 0
    limit = 100  # Maximum limit per API documentation

    while True:
        url = f"{qase_base_url}/case/{project_code}?suite_id={suite_id}&limit={limit}&offset={offset}"
        headers = {"Token": api_token}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            result = response.json().get('result', {})
            cases = result.get('entities', [])
            if not cases:
                break  # No more cases to fetch

            for case in cases:
                test_cases[case['title'].strip().lower()] = case['id']

            offset += limit
        else:
            print(f"Failed to fetch test cases: {response.status_code}, {response.text}")
            break

    return test_cases

# Function to append to the log file for each test case
def update_log_file(log_file_path, test_name, status, details, duration):
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file_path, 'a') as log_file:
        log_file.write(f"\n\nRun at: {current_datetime}\n")
        log_file.write(f"Test Name: {test_name}\nStatus: {status}\nDetails: {details}\nDuration: {duration}\n")

# Fetch data from the database
cursor.execute('SELECT test_name, status, details, duration FROM unit_test_results')
rows = cursor.fetchall()

# Fetch all existing test cases
test_case_mapping = fetch_test_cases(project_code, api_token, suite_id)

# Generate a unique test run name with date and time
current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
unique_run_name = f"{run_name} - {current_datetime}"

# Create a new test run with the unique name
run_id = create_test_run(project_code, api_token, suite_id, unique_run_name)
if not run_id:
    print("Failed to create a test run. Exiting.")
    exit()
else:
    print(f"New test run created with ID: {run_id}")

# Map SQLite statuses to Qase statuses
status_mapping = {
    "passed": "passed",
    "failed": "failed",
    "skipped": "skipped"  # Ensure all possible statuses are covered
}

# Track overall update success
update_success = True

# Process each row from the SQLite database
for row in rows:
    test_name = row[0].strip().lower()
    status = row[1].strip().lower()  # Convert status to lower case for comparison
    details = row[2]
    duration = row[3]
    qase_status = status_mapping.get(status, "skipped")
    
    log_file_name = f"{test_name.replace(' ', '_')}.log"
    log_file_path = os.path.join(log_dir, log_file_name)

    # Append to the log file for this test case
    update_log_file(log_file_path, test_name, qase_status, details, duration)

    # Generate local URL
    local_url = f"http://localhost:8000/{log_file_name}"

    # Read the contents of the log file to include in the Qase comment
    with open(log_file_path, 'r') as log_file:
        log_content = log_file.read()

    # Create the comment with log URL and log contents
    comment = (f"Test '{test_name}' {qase_status.upper()}.\n"
               f"Details: {details}\n\n"
               f"Log URL:\n{local_url}\n\n"
               f"Log Contents:\n{log_content}")

    # Check if the test case exists in Qase, if not, create it
    if test_name not in test_case_mapping:
        case_id = create_test_case(project_code, api_token, suite_id, test_name)
        if case_id:
            test_case_mapping[test_name] = case_id
        else:
            print(f"Failed to create or find test case '{test_name}'. Skipping...")
            continue
    else:
        case_id = test_case_mapping[test_name]

    # Update the test run with the result for this test case, including log contents
    if not update_test_run(project_code, api_token, run_id, case_id, qase_status, comment):
        update_success = False

if update_success:
    print("Update status successfully.")
else:
    print("Some updates failed.")

# Automatically complete the test run
if complete_test_run(project_code, api_token, run_id):
    print("Test run completed successfully.")
else:
    print("Failed to complete the test run.")

# Close the SQLite connection
conn.close()

