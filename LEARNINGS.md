# Learnings

## Day 1 (Saqeeba)

### What I did
- Installed and set up my development environment: Git, Node.js, Python, Docker Desktop and VS Code, plus VS Code extensions (Python, Tailwind CSS IntelliSense, ES7+ React snippets, Docker)
- Practiced the Git workflow in a separate practice repo: branches, commits, pull requests, merging and resolving a merge conflict
- Cloned the helpdesk-platform repo, created my .env from .env.example and ran the full project locally with `docker compose up --build`. Backend (localhost:8000) and frontend (localhost:5173) both worked
- Fixed the .gitignore so .env and __pycache__ are ignored (PR #1)
- Set up GitHub Actions CI for the backend (lint + import check) and frontend (lint + build). All checks passed (PR #8)
- Created a project board with Todo, In Progress, In Review and Done columns
- Created my Week 1 issues
- Read API_CONTRACT.md and prepared questions for Ayesha

### Problem: "Authentication failed" on git push
**Found by:** Saqeeba
**What happened:** An old GitHub login was saved on the laptop, and GitHub no longer allows password authentication for Git operations.
**How I fixed it:** Removed the old GitHub entry from Windows Credential Manager, then signed in through the browser when running git push.
**What I learned:** GitHub requires a browser login or a personal access token, not a password.

### Problem: .env was showing as untracked
**Found by:** Saqeeba
**What happened:** Every line in .gitignore started with leading spaces, so Git was not ignoring .env. Because of the same issue, backend/__pycache__ was also committed to the repo.
**How I fixed it:** Removed the leading spaces, confirmed the fix with `git check-ignore -v .env`, and removed pycache from Git with `git rm -r --cached backend/__pycache__`.
**What I learned:** Every line in .gitignore must start at the very beginning of the line. Also, a file that is already tracked by Git is not removed just by adding it to .gitignore. It has to be untracked with `git rm --cached`.

### Problem: Commands pasted together in PowerShell did not run
**Found by:** Saqeeba
**What happened:** Several git commands were pasted at once and PowerShell showed `>>`, meaning it was waiting for more input instead of running them.
**How I fixed it:** Pressed Ctrl + C and ran each command one by one.
**What I learned:** Paste and run terminal commands one at a time.

### Problem: Project board could not be linked to the repo
**Found by:** Saqeeba
**What happened:** I created the project board under my personal account, but the repo belongs to Ayesha's account. GitHub only lets a personal repo link projects owned by the repo owner, so the board could not be linked and did not show in the repo's Projects tab.
**How it was fixed:** Ayesha created the board from her account so it is linked to the repo, and I removed my duplicate board.
**What I learned:** In a personal repo, only the owner can create a project that is linked to it. Check who owns the repo before creating a board.

## Day 2 (Saqeeba)

### What I did
- Reviewed and approved Ayesha's Dockerfile fix (PR #14) and tested it locally
- Added the database setup (SQLAlchemy, database.py) and Alembic
- Created the Ticket model and the first migration for the tickets table, and checked the table in PostgreSQL
- Added migration checks to CI: single migration head, migrations run on an empty database, and models match migrations

### Problem: ModuleNotFoundError: No module named 'psycopg'
**Found by:** Saqeeba
**What happened:** The newer SQLAlchemy version uses the psycopg (v3) driver for PostgreSQL by default, but psycopg2-binary was installed.
**How I fixed it:** Replaced psycopg2-binary with psycopg[binary] in requirements.txt and rebuilt the Docker image.
**What I learned:** Read the last line of a traceback first, it usually names the real problem.