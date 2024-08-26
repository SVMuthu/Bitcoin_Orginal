import json
import sqlite3
import requests
import re
import os
from datetime import datetime

# Define the absolute path to the JSON file and database
script_dir = os.path.dirname(os.path.abspath(__file__))
config_file_path = os.path.join(script_dir, 'functional_test_config.json')

# Load configuration from JSON file
with open(config_file_path, 'r') as config_file:
        config = json.load(config_file)

# Extract configuration details
db_path = config.get('db_path')
api_token = config.get('api_token')
project_code = config.get('project_code')
qase_base_url = config.get('qase_base_url')
suite_id = config.get('suite_id')
suite_name = config.get('suite_name', 'Default Suite Name')
log_file_path = config.get('log_file_path')
run_name = config.get('run_name')

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

# Function to update the test run with results and description
def update_test_run(project_code, api_token, run_id, case_id, status, description):
    url = f"{qase_base_url}/result/{project_code}/{run_id}"
    headers = {"Content-Type": "application/json", "Token": api_token}
    payload = {
        "case_id": case_id,
        "status": status,
        "description": description  
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.status_code == 200

# Function to complete the test run
def complete_test_run(project_code, api_token, run_id):
    url = f"{qase_base_url}/run/{project_code}/{run_id}/complete"
    headers = {"Content-Type": "application/json", "Token": api_token}
    response = requests.post(url, headers=headers)
    return response.status_code == 200

# Function to fetch existing test cases from Qase with pagination
def fetch_functional_test_cases(project_code, api_token, suite_id):
    test_cases = {}
    offset = 0
    limit = 100  

    while True:
        url = f"{qase_base_url}/case/{project_code}?suite_id={suite_id}&limit={limit}&offset={offset}"
        headers = {"Token": api_token}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            result = response.json().get('result', {})
            cases = result.get('entities', [])
            if not cases:
                break  

            for case in cases:
                test_cases[case['title'].strip().lower()] = case['id']

            offset += limit
        else:
            print(f"Failed to fetch test cases: {response.status_code}, {response.text}")
            break

    return test_cases

# Fetch data from the database
cursor.execute('SELECT test_name, status, details FROM functional_test_results')
rows = cursor.fetchall()

# Fetch all existing test cases
test_case_mapping = fetch_functional_test_cases(project_code, api_token, suite_id)

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
    "not executed": "skipped"
}

# Track overall update success
update_success = True

# Process each row from the SQLite database
for row in rows:
    test_name = row[0].strip().lower()
    status = row[1].strip().lower()  # Normalize status value
    duration = row[2] if row[2] else 'N/A'  # Handle missing duration
    qase_status = status_mapping.get(status, "skipped")
    description = f"{test_name} {qase_status}, Duration: {duration}"

    if test_name in test_case_mapping:
        case_id = test_case_mapping[test_name]
        # Update the test run with the result for existing test cases and the description
        if not update_test_run(project_code, api_token, run_id, case_id, qase_status, description):
            update_success = False

# Mark the test run as complete
if not complete_test_run(project_code, api_token, run_id):
    print(f"Failed to complete the test run with ID: {run_id}")

if update_success:
    print("Update status successfully.")
else:
    print("Some updates failed.")

# Close the SQLite connection
conn.close()

