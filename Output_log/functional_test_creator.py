import json
import sqlite3
import requests
import re
import os

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

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Ensure the table exists with the correct structure
cursor.execute('''
    CREATE TABLE IF NOT EXISTS functional_test_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_name TEXT UNIQUE,
        status TEXT,
        details TEXT,
        duration TEXT
    )
''')

# Function to check if a specific test is already in the database
def test_exists(test_name):
    cursor.execute('SELECT 1 FROM functional_test_results WHERE test_name = ?', (test_name,))
    return cursor.fetchone() is not None

# Function to insert data into the table
def insert_data(test_name, status, details, duration):
    if not test_exists(test_name):
        cursor.execute('''
            INSERT INTO functional_test_results (test_name, status, details, duration)
            VALUES (?, ?, ?, ?)
        ''', (test_name, status, details, duration))
        conn.commit()
        return True
    return False

# Function to parse and insert data from log lines
def process_log_line(line):
    pattern = re.compile(r'(\d+)/(\d+) - (.+?) (passed|skipped),? (.*?)(?:, Duration: (.+))?$')
    match = pattern.match(line.strip())
    if match:
        count, total, test_name, status, details, duration = match.groups()
        description = f"{test_name} -- {details.strip()} Duration: {duration}"
        inserted = insert_data(test_name, status, details.strip(), duration)
        return test_name, description, inserted
    return None, None, False

# Process log file
inserted_count = 0
try:
    with open(log_file_path, 'r') as log_file:
        for line in log_file:
            test_name, description, inserted = process_log_line(line)
            if inserted:
                inserted_count += 1
except FileNotFoundError:
    print(f"Error: The log file '{log_file_path}' was not found.")
    exit(1)

cursor.execute('SELECT test_name FROM functional_test_results')
existing_tests = set(row[0].strip().lower() for row in cursor.fetchall())

# Function to check if a test suite exists
def check_test_suite_exists(project_code, api_token, suite_id):
    url = f"{qase_base_url}/suite/{project_code}/{suite_id}"
    headers = {"Token": api_token}
    response = requests.get(url, headers=headers)
    return response.status_code == 200

# Function to create a new test suite
def create_test_suite(project_code, api_token, suite_name):
    url = f"{qase_base_url}/suite/{project_code}"
    headers = {"Content-Type": "application/json", "Token": api_token}
    payload = {"title": suite_name, "description": "Created by functional_test_runner"}
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json().get('result', {}).get('id')
    else:
        print(f"Failed to create test suite: {response.status_code}, {response.text}")
        return None

def update_suite_id_in_config(config_path, new_suite_id):
    with open(config_path, 'r+') as config_file:
        config = json.load(config_file)
        config['suite_id'] = new_suite_id
        config_file.seek(0) 
        json.dump(config, config_file, indent=4)
        config_file.truncate() 

# Function to fetch existing test cases from Qase with pagination
def fetch_test_cases(project_code, api_token, suite_id):
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

# Function to create a new test case in Qase
def create_test_case(project_code, api_token, test_case_data):
    url = f"{qase_base_url}/case/{project_code}"
    headers = {"Content-Type": "application/json", "Token": api_token}
    response = requests.post(url, headers=headers, json=test_case_data)
    if response.status_code == 200:
        return response.json().get('result', {}).get('id')
    else:
        print(f"Failed to create test case: {response.status_code}, {response.text}")
        return None

# Check if the test suite exists
suite_exists = check_test_suite_exists(project_code, api_token, suite_id)

# Print the status of the test suite
if suite_exists:
    print(f"Test suite with ID {suite_id} exists.")
else:
    print(f"Test suite with ID {suite_id} does not exist. Creating a new test suite.")
    new_suite_id = create_test_suite(project_code, api_token, suite_name)
    if new_suite_id:
        print(f"New test suite created with ID {new_suite_id}. Updating config file.")
        update_suite_id_in_config(config_file_path, new_suite_id)
        suite_id = new_suite_id
    else:
        print("Failed to create a new test suite. Exiting.")
        exit()

# Fetch all existing test cases in the suite
test_case_mapping = fetch_test_cases(project_code, api_token, suite_id)

# Flag to determine if any new test cases were created
test_cases_created = False
new_test_cases_count = 0

# Process each row from the SQLite database
for row in cursor.execute('SELECT test_name, status, details, duration FROM functional_test_results'):
    test_name = row[0].strip().lower()
    if test_name not in test_case_mapping:
        # Prepare the payload for the test case
        test_case_data = {
            "title": test_name,
            "description": f"{row[1]} -- {row[2]}, Duration: {row[3]}",
            "preconditions": "N/A",
            "postconditions": "N/A",
            "severity": 3,
            "priority": 2, 
            "suite_id": suite_id,
            "custom_fields": {
                "details": row[2],
                "duration": row[3]
            }
        }

        # Create the test case
        case_id = create_test_case(project_code, api_token, test_case_data)
        if case_id:
            test_cases_created = True
            new_test_cases_count += 1

# Final message based on whether any new test cases were created
if inserted_count == 0:
    print("No new data was inserted.")
else:
    print(f"{inserted_count} new rows inserted into the database.")

if not test_cases_created:
    print("All test cases already exist in Qase.")
else:
    print(f"{new_test_cases_count} new test cases were created in Qase.")

# Close the SQLite connection
conn.close()

