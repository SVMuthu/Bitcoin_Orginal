import json
import sqlite3
import re
import os
import requests
from datetime import datetime

# Define the absolute path to the JSON file and database
script_dir = os.path.dirname(os.path.abspath(__file__))
config_file_path = os.path.join(script_dir, 'unit_test_config.json')

# Load configuration from JSON file
with open(config_file_path, 'r') as config_file:
    config = json.load(config_file)

# Extract configuration details
db_path = config.get('db_path')
log_file_path = config.get('log_file_path')
qase_base_url = config.get('qase_base_url')
project_code = config.get('project_code')
api_token = config.get('api_token')
suite_id = config.get('suite_id')
suite_name = config.get('suite_name')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Ensure the main table exists with the correct structure
cursor.execute('''
    CREATE TABLE IF NOT EXISTS unit_test_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_name TEXT,
        status TEXT,
        details TEXT,
        duration TEXT,
        processed BOOLEAN DEFAULT 0,
        timestamp TEXT,
        UNIQUE (test_name, status, details, duration, timestamp)
    )
''')

# Create or recreate the temporary table
cursor.execute('DROP TABLE IF EXISTS temp_unit_test_results')

cursor.execute('''
    CREATE TEMPORARY TABLE temp_unit_test_results (
        test_name TEXT,
        status TEXT,
        details TEXT,
        duration TEXT,
        timestamp TEXT,
        UNIQUE (test_name, status, details, duration, timestamp)
    )
''')

def insert_data_into_temp(test_name, status, details, duration):
    try:
        timestamp = datetime.now().isoformat()
        cursor.execute('''
            INSERT OR REPLACE INTO temp_unit_test_results (test_name, status, details, duration, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (test_name, status, details, duration, timestamp))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error inserting data into temp table: {e}")
        return False

def process_log_line(line):
    running_pattern = re.compile(r'Running tests: (.+?) from (.+?)\.(cpp|h|py|java|c|rb|go|php)')
    skipped_pattern = re.compile(r'Test suite "(.+?)" (is skipped|is disabled)')
    failed_pattern = re.compile(r'error: in "(.+?)"')
    core_dump_pattern = re.compile(r'core dumped')

    duration = '0s'

    if core_dump_pattern.search(line):
        test_name = "unknown"
        return test_name, 'failed - core dumped', 'Core dump occurred', duration

    match = running_pattern.search(line)
    if match:
        test_name = match.group(1).strip()
        details = f"Source file: {match.group(2)}.{match.group(3)}"
        return test_name, 'passed', details, duration

    match = failed_pattern.search(line)
    if match:
        test_name = match.group(1).strip()
        return test_name, 'failed', 'Error occurred', duration

    match = skipped_pattern.search(line)
    if match:
        test_name = match.group(1).strip()
        return test_name, 'skipped', 'Test suite skipped or disabled', duration
    
    return None, None, None, duration

def update_original_table():
    try:
        # Begin the transaction
        conn.execute('BEGIN')

        # Update existing records in the original table
        cursor.execute('''
            UPDATE unit_test_results
            SET status = (SELECT status FROM temp_unit_test_results
                          WHERE temp_unit_test_results.test_name = unit_test_results.test_name
                            AND temp_unit_test_results.details = unit_test_results.details
                            AND temp_unit_test_results.duration = unit_test_results.duration
                            AND temp_unit_test_results.timestamp = unit_test_results.timestamp),
                details = (SELECT details FROM temp_unit_test_results
                           WHERE temp_unit_test_results.test_name = unit_test_results.test_name
                             AND temp_unit_test_results.status = unit_test_results.status
                             AND temp_unit_test_results.duration = unit_test_results.duration
                             AND temp_unit_test_results.timestamp = unit_test_results.timestamp),
                duration = (SELECT duration FROM temp_unit_test_results
                            WHERE temp_unit_test_results.test_name = unit_test_results.test_name
                              AND temp_unit_test_results.status = unit_test_results.status
                              AND temp_unit_test_results.details = unit_test_results.details
                              AND temp_unit_test_results.timestamp = unit_test_results.timestamp),
                timestamp = (SELECT timestamp FROM temp_unit_test_results
                             WHERE temp_unit_test_results.test_name = unit_test_results.test_name
                               AND temp_unit_test_results.status = unit_test_results.status
                               AND temp_unit_test_results.details = unit_test_results.details
                               AND temp_unit_test_results.duration = temp_unit_test_results.duration)
            WHERE EXISTS (SELECT 1 FROM temp_unit_test_results
                          WHERE temp_unit_test_results.test_name = unit_test_results.test_name
                            AND temp_unit_test_results.status = unit_test_results.status
                            AND temp_unit_test_results.details = unit_test_results.details
                            AND temp_unit_test_results.duration = unit_test_results.duration
                            AND temp_unit_test_results.timestamp = unit_test_results.timestamp)
        ''')

        # Insert new records into the original table
        cursor.execute('''
            INSERT INTO unit_test_results (test_name, status, details, duration, processed, timestamp)
            SELECT test_name, status, details, duration, 0, timestamp
            FROM temp_unit_test_results
            WHERE NOT EXISTS (
                SELECT 1 FROM unit_test_results
                WHERE unit_test_results.test_name = temp_unit_test_results.test_name
                  AND unit_test_results.status = temp_unit_test_results.status
                  AND unit_test_results.details = temp_unit_test_results.details
                  AND unit_test_results.duration = temp_unit_test_results.duration
                  AND unit_test_results.timestamp = temp_unit_test_results.timestamp
            )
        ''')

        # Mark processed rows as processed
        cursor.execute('''
            UPDATE unit_test_results
            SET processed = 1
            WHERE EXISTS (
                SELECT 1 FROM temp_unit_test_results
                WHERE temp_unit_test_results.test_name = unit_test_results.test_name
                  AND temp_unit_test_results.status = unit_test_results.status
                  AND temp_unit_test_results.details = unit_test_results.details
                  AND temp_unit_test_results.duration = unit_test_results.duration
                  AND temp_unit_test_results.timestamp = unit_test_results.timestamp
            )
        ''')

        # Commit the transaction
        conn.execute('COMMIT')
        return True

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error updating the original table: {e}")
        return False

def test_exists(test_name):
    cursor.execute('SELECT 1 FROM unit_test_results WHERE test_name = ? AND processed = 1', (test_name,))
    return cursor.fetchone() is not None

# Process the log file and insert data into the temporary table
inserted_count = 0
with open(log_file_path, 'r') as log_file:
    for line in log_file:
        test_name, status, details, duration = process_log_line(line)
        if test_name and not test_exists(test_name):
            inserted = insert_data_into_temp(test_name, status, details, duration)
            if inserted:
                inserted_count += 1

# Update the original table with data from the temp table
update_successful = update_original_table()

# Fetch data from the database
cursor.execute('SELECT test_name FROM unit_test_results')
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
    payload = {"title": suite_name, "description": "Created by unit_test_runner"}
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
        config_file.seek(0)  # Move the cursor to the start of the file
        json.dump(config, config_file, indent=4)
        config_file.truncate()  # Truncate the file to the new length

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
        update_suite_id_in_config('unit_test_config.json', new_suite_id)
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
for row in cursor.execute('SELECT test_name, status, details, duration FROM unit_test_results'):
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
