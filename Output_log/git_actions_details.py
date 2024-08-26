# all_in_one.py
import requests
import sqlite3

def create_schema():
    db_path = '/home/svm/Downloads/Bitcoin_Core_Qase/qase.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commits (
            id TEXT PRIMARY KEY,
            author TEXT,
            message TEXT,
            date TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commit_files (
            commit_id TEXT,
            file_name TEXT,
            status TEXT,
            FOREIGN KEY (commit_id) REFERENCES commits(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS action_runners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            runner_id TEXT,
            name TEXT,
            os TEXT,
            status TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def store_commits():
    GITHUB_TOKEN = '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'
    REPO_OWNER = 'SVMuthu'
    REPO_NAME = 'Bitcoin_Orginal'
    API_URL = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/commits'

    headers = {
        'Authorization': f'token {GITHUB_TOKEN}'
    }

    db_path = '/var/lib/grafana/logs.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    response = requests.get(API_URL, headers=headers)
    if response.status_code == 200:
        commits = response.json()
        for commit in commits:
            commit_id = commit['sha']
            author = commit['commit']['author']['name']
            message = commit['commit']['message']
            date = commit['commit']['author']['date']

            cursor.execute('''
                INSERT OR REPLACE INTO commits (id, author, message, date)
                VALUES (?, ?, ?, ?)
            ''', (commit_id, author, message, date))

            files_url = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/commits/{commit_id}'
            files_response = requests.get(files_url, headers=headers)
            if files_response.status_code == 200:
                files_data = files_response.json()
                for file in files_data.get('files', []):
                    file_name = file['filename']
                    status = file['status']
                    cursor.execute('''
                        INSERT INTO commit_files (commit_id, file_name, status)
                        VALUES (?, ?, ?)
                    ''', (commit_id, file_name, status))

    conn.commit()
    conn.close()

def store_runners():
    GITHUB_TOKEN = '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'
    REPO_OWNER = 'SVMuthu'
    REPO_NAME = 'Bitcoin_Orginal'
    ACTION_RUNNERS_URL = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/runners'

    headers = {
        'Authorization': f'token {GITHUB_TOKEN}'
    }

    db_path = '/var/lib/grafana/logs.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    response = requests.get(ACTION_RUNNERS_URL, headers=headers)
    if response.status_code == 200:
        runners = response.json().get('runners', [])
        for runner in runners:
            runner_id = runner['id']
            name = runner['name']
            os = runner['os']
            status = runner['status']
            cursor.execute('''
                INSERT OR REPLACE INTO action_runners (runner_id, name, os, status)
                VALUES (?, ?, ?, ?)
            ''', (runner_id, name, os, status))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_schema()
    store_commits()
    store_runners()

