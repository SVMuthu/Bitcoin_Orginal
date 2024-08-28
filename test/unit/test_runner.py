#!/usr/bin/env python3

import re
import subprocess
import os

def process_log_line(line):
    # Define patterns
    running_pattern = re.compile(r'Running tests: (.+?) from (.+?\.(?:cpp|h|py|java|c|rb|go|php))')
    skipped_pattern = re.compile(r'Test suite "(.+?)" (is skipped(?: because .*)?|is disabled)')
    failed_pattern = re.compile(r'error: in "(.+?)"')
    core_dump_pattern = re.compile(r'(?:core dumped|Aborted \(core dumped\))')
    duration_pattern = re.compile(r'testing time: (\d+)us')

    # Default values
    duration = '0s'
    description = ''

    # Check for core dump
    if core_dump_pattern.search(line):
        test_name = "unknown"
        description = 'Core dump occurred'
        return test_name, 'failed - core dumped', description, duration

    # Check for failed tests
    match = failed_pattern.search(line)
    if match:
        test_name = match.group(1).strip()
        description = 'Test failed due to an error.'
        return test_name, 'failed', description, duration

    # Check for skipped tests
    match = skipped_pattern.search(line)
    if match:
        test_name = match.group(1).strip()
        description = match.group(2).strip()
        return test_name, 'skipped', description, duration

    # Check for running tests
    match = running_pattern.search(line)
    if match:
        test_name = match.group(1).strip()
        test_file = match.group(2).strip()
        return f"{test_name} from {test_file}", 'passed', description, duration

    # Check for duration
    match = duration_pattern.search(line)
    if match:
        duration = f"{int(match.group(1)) // 1000}s"

    return None, None, None, duration

def process_and_display(logs, log_file):
    # Initialize variables
    test_cases = []
    total_count = 0

    # First pass to count total test cases
    for line in logs:
        test_name, status, description, duration = process_log_line(line)
        if test_name:
            total_count += 1

    test_number = 0
    # Second pass to format output with the correct test number/total count
    for line in logs:
        test_name, status, description, duration = process_log_line(line)
        if test_name:
            test_number += 1
            if status in ['failed', 'skipped']:
                test_case = f"{test_number}/{total_count} - {test_name}, {status}, Duration: {duration}, ({description})"
            else:
                test_case = f"{test_number}/{total_count} - {test_name}, {status}, Duration: {duration}"
            
            test_cases.append(test_case)
            print(test_case)
            log_file.write(test_case + '\n')  # Write only the formatted line to the log file
    
    # Write total test cases to the log file
    summary = f"\nUnit Test Cases ({total_count} total cases)"
    print(summary)
    log_file.write(summary + '\n')

def run_make_check():
    # Save the current working directory
    original_dir = os.getcwd()

    # Create or overwrite the log file
    with open('test/unit/unit_test_cases.log', 'w') as log_file:
        try:
            # Change to the parent directory (if needed)
           # os.chdir('../..')

            # Run the make check command
            process = subprocess.Popen(['make', 'check', '-j', '$(nproc)'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

            logs = []
            for line in process.stdout:
                if process_log_line(line)[0]:  # Only add relevant lines
                    print(line, end='')  # Print the make check output in real-time
                    logs.append(line)

            # Wait for the command to complete
            process.wait()

            # Process and display the results, and write only the summary to the log file
            print("\nUnit Test Cases...")
            process_and_display(logs, log_file)

        finally:
            # Restore the original working directory
            os.chdir(original_dir)

if __name__ == "__main__":
    run_make_check()

