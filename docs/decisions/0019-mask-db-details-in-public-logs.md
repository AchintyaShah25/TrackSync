# 0019: Mask database connection details in public workflow logs

- **Status:** Accepted
- **Date:** 2026-11-15
- **Milestone:** 1

## Context
The repo is public (it is a portfolio project), so GitHub Actions run logs are readable
by anyone. The ETL workflow gets the production connection string from the secret
`ETL_DATABASE_URL`. GitHub masks a secret only as a whole string. Parts of it, such as the
pooler host or the username `postgres.<project-ref>`, can still appear in a database error
message. The password is never printed (SQLAlchemy and psycopg redact it), but the owner
does not want any production connection detail public.

## Options considered
1. **Make the repo private**: hides logs completely, but reviewers lose the code.
2. **Accept the exposure**: host and project ref are not credentials on their own, but
   they help an attacker target the database and the owner does not want them public.
3. **Mask the parts at the start of each run** with `::add-mask::`: a few lines of shell,
   no new dependency, keeps the repo public.

## Decision
Option 3. The first step of the ETL job parses `DATABASE_URL` and masks the username,
the host, and the bare project ref before any other step runs. The values are only ever
passed to `add-mask`, never echoed.

## Consequences
- Any later step that prints these values shows `***` instead.
- Masking only covers this workflow. Any new workflow that uses a database secret needs
  the same step (or a shared composite action, if we get a second one).
- The CI workflow uses throwaway local databases and needs no masking.
