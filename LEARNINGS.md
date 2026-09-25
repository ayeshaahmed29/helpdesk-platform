# Learnings

### Problem: "Authentication failed" on git push
**What happened:** An old GitHub login was saved on the laptop, and GitHub no longer allows password authentication for Git operations.
**How we fixed it:** Removed the old GitHub entry from Windows Credential Manager, then signed in through the browser when running git push.
**What we learned:** GitHub requires a browser login or a personal access token, not a password.

### Problem: .env was showing as untracked
**What happened:** Every line in .gitignore started with leading spaces, so Git was not ignoring .env. Because of the same issue, backend/__pycache__ was also committed to the repo.
**How we fixed it:** Removed the leading spaces, confirmed the fix with `git check-ignore -v .env`, and removed pycache from Git with `git rm -r --cached backend/__pycache__`.
**What we learned:** Every line in .gitignore must start at the very beginning of the line. Also, a file that is already tracked by Git is not removed just by adding it to .gitignore. It has to be untracked with `git rm --cached`.