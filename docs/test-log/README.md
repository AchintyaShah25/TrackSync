# Test log

One file per day: `YYYY-MM-DD.md`. Append an entry after every test run during a task.

## Entry format

```
### HH:MM: <task or feature name>
- **Command:** make test (or the specific pytest/vitest command)
- **Scope:** which packages or test files
- **Result:** N passed, N failed, N skipped
- **Failures:** test name → root cause → fix applied (or "none")
- **Tests added/changed:** file::test_name — what it checks
- **Notes:** flaky tests, follow-ups, coverage gaps
```
