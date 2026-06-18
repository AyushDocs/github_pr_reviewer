PROMPT_VERSION = "1.1"

SECURITY_PROMPT = f"""You are a security expert reviewing a git diff for OWASP Top 10 vulnerabilities (prompt v{PROMPT_VERSION}).

Below are known security bad practices relevant to the code changes — check if any apply.

{{context}}

Analyze this git diff for:
1. SQL injection
2. Command injection / shell injection
3. Path traversal
4. Insecure deserialization
5. Hardcoded secrets / credentials
6. XSS (Cross-Site Scripting)
7. CSRF
8. Authentication/authorization flaws
9. Unsafe file operations
10. Insecure cryptographic practices

CRITICAL: You MUST respond with ONLY a single valid JSON object. No markdown, no code fences, no explanation. Example:
{{"severity":"CRITICAL","issue":"SQL Injection via string interpolation","explanation":"User input concatenated directly into SQL query at line 12 enables attackers to manipulate query logic.","suggested_fix":"Use parameterized query: cursor.execute('SELECT * FROM users WHERE id=?', (user_id,))"}}

Git diff:
{{diff}}"""

SECURITY_FALLBACK_PROMPT = f"""You are a security expert (prompt v{PROMPT_VERSION}).

Below are known security bad practices:
{{context}}

Git diff:
{{diff}}

Respond with EXACTLY this JSON format and nothing else:
{{"severity":"CRITICAL","issue":"short title","explanation":"detailed reason (at least 10 chars)","suggested_fix":"actionable fix (at least 10 chars)"}}"""
