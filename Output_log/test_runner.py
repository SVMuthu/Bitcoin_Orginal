import re

def process_log_line(line):
    # Define patterns
    running_pattern = re.compile(r'Running tests: (.+?) from (.+?)\.(cpp|h|py|java|c|rb|go|php)')
    skipped_pattern = re.compile(r'Test suite "(.+?)" (is skipped|is disabled)')
    failed_pattern = re.compile(r'error: in "(.+?)"')
    core_dump_pattern = re.compile(r'core dumped')
    duration_pattern = re.compile(r'testing time: (\d+)us')

    # Default values
    duration = '0s'
    description = ''

    # Check for core dump
    if core_dump_pattern.search(line):
        test_name = "unknown"
        return test_name, 'failed - core dumped', 'Core dump occurred', duration

    # Check for failed tests
    match = failed_pattern.search(line)
    if match:
        test_name = match.group(1).strip()
        description = 'Error occurred'
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
        return test_name, 'passed', description, duration

    # Check for duration
    match = duration_pattern.search(line)
    if match:
        duration = f"{int(match.group(1)) // 1000}s"
    
    return None, None, None, duration

def count_total_cases(log_file_path):
    try:
        with open(log_file_path, 'r') as file:
            logs = file.readlines()
    except FileNotFoundError:
        print(f"Error: The file {log_file_path} was not found.")
        return 0

    # Initialize variables
    total_count = 0

    for line in logs:
        test_name, status, description, duration = process_log_line(line)
        if test_name:
            total_count += 1

    return total_count

def process_log_file(log_file_path):
    try:
        with open(log_file_path, 'r') as file:
            logs = file.readlines()
    except FileNotFoundError:
        print(f"Error: The file {log_file_path} was not found.")
        return [], 0

    # Get the total number of cases
    total_count = count_total_cases(log_file_path)

    # Initialize variables
    test_cases = []
    test_number = 0

    for line in logs:
        test_name, status, description, duration = process_log_line(line)
        if test_name:
            test_number += 1
            # Append description only for failed or skipped tests
            if status in ['failed', 'skipped']:
                test_cases.append(f"{test_number}/{total_count} - {test_name}, {status}, Duration: {duration}, ({description})")
            else:
                test_cases.append(f"{test_number}/{total_count} - {test_name}, {status}, Duration: {duration}")
    
    return test_cases, total_count

if __name__ == "__main__":
    log_file_path = "unit_test.log"  # Replace with your log file path

    formatted_logs, total_count = process_log_file(log_file_path)

    # Print total count first
    print(f"Total Cases: {total_count}")

    # Print formatted logs
    if formatted_logs:
        for log in formatted_logs:
            print(log)
    else:
        print("No test cases found or file processing failed.")

