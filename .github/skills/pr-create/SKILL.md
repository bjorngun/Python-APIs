---
name: pr-create
description: "Create a pull request for the current branch. Use when: opening a PR, submitting for review, creating a draft PR, preparing a PR description, pushing and creating a pull request."
argument-hint: "Say 'create PR', 'draft PR', or 'PR for #42'"
---

# Create Pull Request

Pushes the current branch and creates a GitHub pull request with a structured description.

## When to Use

- Work is done on a feature branch and ready for review.
- User says "create a PR", "open a pull request", or "submit for review".
- User wants a draft PR for early feedback.

## Procedure

### 1. Gather Context

1. Run `git fetch origin main`.
2. Run `git log origin/main..HEAD --oneline` and `git diff origin/main --stat` to understand
   changes against remote.
3. Check branch name and commit messages for a GitHub issue reference (for example `#42`).
4. Check for uncommitted changes and ask user whether to commit first.
5. Rebase current branch onto `origin/main` using `git rebase origin/main`.
   - If rebase conflicts occur, stop and inform the user.
6. Check for unpushed commits and push before creating PR.
   - Use `--force-with-lease` after rebase if required.

### 2. Build the PR Description

Use this structure:

```markdown
## Description
<!-- What and why - the problem being solved -->

## Changes
<!-- Bullet list of key changes with file/function references -->

## Testing
<!-- Concrete steps a reviewer can follow to verify -->
```

If a GitHub issue is linked, add `Closes #X` or `Relates to #X` at the end.

### 3. Build the PR Title

- Format: `{type}: {short description}` (for example `feat: add AD envelope response model`).
- If issue linked: `{type}(#{issue}): {short description}`.
- Keep title under 72 characters.
- Match conventional commit style used in the repository.

### 4. SemVer Label Check

Before creating PR, ensure exactly one SemVer intent is present in PR title/body notes or user
intent so the eventual PR can be labeled correctly:
- `semver:major`
- `semver:minor`
- `semver:none`

If SemVer impact is unclear, ask user before creating PR.

### 5. Create the Pull Request

Use `github-pull-request_create_pull_request`:
- `head`: current branch name only.
- `base`: `main` unless user specifies otherwise.
- `title`: from Step 3.
- `body`: from Step 2.
- `draft`: `true` only if user asks for draft.

### 6. Confirm

Report:
- PR number and link.
- Base branch.
- If draft, remind user to mark ready for review.

## Guidelines

- Target `main` by default.
- PR description should be in English.
- Do not create PR if there are no commits ahead of `origin/main`; inform user.
- Respect repository release flow: remind user to set exactly one SemVer label
  (`semver:major`, `semver:minor`, or `semver:none`).
