"""Ground-truth test cases for regression testing the PR reviewer.

Each test case defines a set of PR diffs and the expected issues the
reviewer should flag. Expected fields:
  - file: filename the issue should appear in
  - severity: expected severity level
  - issue_contains: substring expected in the issue title
  - type: "code" (from review_chain) or "security" (from security_chain)
"""

TEST_CASES = [
    {
        "name": "sql_injection",
        "diffs": [
            {
                "filename": "app/login.py",
                "patch": (
                    " def login(username, password):\n"
                    "+    query = f\"SELECT * FROM users WHERE username='{username}' AND password='{password}'\"\n"
                    "+    cursor.execute(query)\n"
                    "+    return cursor.fetchone()\n"
                ),
            },
        ],
        "expected": [
            {"file": "app/login.py", "severity": "CRITICAL", "issue_contains": "SQL", "type": "security"},
        ],
    },
    {
        "name": "hardcoded_secret",
        "diffs": [
            {
                "filename": "config/settings.py",
                "patch": (
                    " # Database configuration\n"
                    "+DB_PASSWORD = 'supersecret123'\n"
                    "+API_SECRET = 'sk-live-a1b2c3d4'\n"
                ),
            },
        ],
        "expected": [
            {"file": "config/settings.py", "severity": "CRITICAL", "issue_contains": "secret", "type": "security"},
            {"file": "config/settings.py", "severity": "CRITICAL", "issue_contains": "secret", "type": "code"},
        ],
    },
    {
        "name": "command_injection",
        "diffs": [
            {
                "filename": "utils/runner.py",
                "patch": (
                    " def run_cmd(user_input):\n"
                    "+    result = os.system(f'ping -c 1 {user_input}')\n"
                    "+    return result\n"
                ),
            },
        ],
        "expected": [
            {"file": "utils/runner.py", "severity": "CRITICAL", "issue_contains": "injection", "type": "security"},
            {"file": "utils/runner.py", "severity": "CRITICAL", "issue_contains": "injection", "type": "code"},
        ],
    },
    {
        "name": "path_traversal",
        "diffs": [
            {
                "filename": "api/files.py",
                "patch": (
                    " def read_file(filename):\n"
                    "+    path = '/var/data/' + filename\n"
                    "+    with open(path) as f:\n"
                    "+        return f.read()\n"
                ),
            },
        ],
        "expected": [
            {"file": "api/files.py", "severity": "HIGH", "issue_contains": "traversal", "type": "security"},
        ],
    },
    {
        "name": "bare_except",
        "diffs": [
            {
                "filename": "worker/task.py",
                "patch": (
                    " def process(data):\n"
                    "+    try:\n"
                    "+        result = do_work(data)\n"
                    "+    except:\n"
                    "+        pass\n"
                    "+    return result\n"
                ),
            },
        ],
        "expected": [
            {"file": "worker/task.py", "severity": "MEDIUM", "issue_contains": "except", "type": "code"},
        ],
    },
    {
        "name": "eval_usage",
        "diffs": [
            {
                "filename": "tools/calculator.py",
                "patch": (
                    " def calculate(expr):\n"
                    "+    return eval(expr)\n"
                ),
            },
        ],
        "expected": [
            {"file": "tools/calculator.py", "severity": "CRITICAL", "issue_contains": "eval", "type": "security"},
            {"file": "tools/calculator.py", "severity": "CRITICAL", "issue_contains": "eval", "type": "code"},
        ],
    },
    {
        "name": "insecure_crypto",
        "diffs": [
            {
                "filename": "auth/hash.py",
                "patch": (
                    " def hash_password(pw):\n"
                    "+    import hashlib\n"
                    "+    return hashlib.md5(pw.encode()).hexdigest()\n"
                ),
            },
        ],
        "expected": [
            {"file": "auth/hash.py", "severity": "HIGH", "issue_contains": "md5", "type": "security"},
            {"file": "auth/hash.py", "severity": "HIGH", "issue_contains": "md5", "type": "code"},
        ],
    },
    {
        "name": "multi_file_pr",
        "diffs": [
            {
                "filename": "app/db.py",
                "patch": (
                    " def get_user(uid):\n"
                    "+    query = f\"SELECT * FROM users WHERE id={uid}\"\n"
                    "+    return execute(query)\n"
                ),
            },
            {
                "filename": "app/config.py",
                "patch": (
                    " # AWS credentials\n"
                    "+AWS_ACCESS_KEY = 'AKIAIOSFODNN7EXAMPLE'\n"
                    "+AWS_SECRET_KEY = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'\n"
                ),
            },
        ],
        "expected": [
            {"file": "app/db.py", "severity": "CRITICAL", "issue_contains": "SQL", "type": "security"},
            {"file": "app/config.py", "severity": "CRITICAL", "issue_contains": "secret", "type": "security"},
            {"file": "app/config.py", "severity": "CRITICAL", "issue_contains": "secret", "type": "code"},
        ],
    },
    {
        "name": "clean_pr",
        "diffs": [
            {
                "filename": "app/hello.py",
                "patch": (
                    " def greet(name):\n"
                    "+    return f'Hello, {name}!'\n"
                ),
            },
        ],
        "expected": [],
    },
]


def get_test_case(name):
    for tc in TEST_CASES:
        if tc["name"] == name:
            return tc
    return None
