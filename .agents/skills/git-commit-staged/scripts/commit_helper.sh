#!/bin/bash
# Helper script for the git-commit-staged skill to verify staging and display status.

# Check if we are inside a git repository
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: Not a git repository."
  exit 1
fi

# Check if there are any staged changes
if git diff --cached --quiet; then
  echo "No changes currently staged for commit."
  echo ""
  echo "Modified/Untracked files in workspace:"
  git status -s
  echo ""
  echo "Please stage files using 'git add <file>' before committing."
  exit 1
fi

# Print status of staged changes
echo "Staged changes to be committed:"
git diff --cached --name-status
exit 0
