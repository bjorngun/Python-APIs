---
name: pr-comments
description: "Review and address PR comments on the active pull request. Use when: addressing review feedback, fixing PR comments, resolving review threads, implementing requested changes, handling Copilot review suggestions."
argument-hint: "Say 'address PR comments', 'fix review feedback', or 'handle PR review'"
---

# Address PR Review Comments

Fetches unresolved review comments on the active PR, validates each one against the current
codebase, applies correct fixes, and prompts user when comments are ambiguous or changes are large.

## When to Use

- Reviewer (human or Copilot) left comments on active PR.
- User says "fix review comments", "address PR feedback", or "handle PR comments".

## Procedure

### 1. Fetch the PR and Comments

Use `github-pull-request_currentActivePullRequest` with `refresh: true`.

Extract:
- `reviewThreads`: focus on unresolved threads where `isResolved` is `false`.
- `timelineComments`: general PR comments where `commentType` is `CHANGES_REQUESTED` or
  `COMMENTED`.
- `changes`: file diff context.

If no unresolved comments remain, inform user and stop.

### 2. Validate Each Comment Against the Codebase

For each unresolved comment:

1. Read relevant file and line context from current workspace.
2. Understand concern type: bug, style, security, logic, refactor, etc.
3. Cross-check related code and patterns for correctness.
4. Classify:
   - **Valid and small**: correct and safe small fix -> apply automatically.
   - **Valid and large**: correct but significant change -> ask user first.
   - **Uncertain**: unclear or potentially incorrect -> ask user with analysis.
   - **Invalid**: factually incorrect or not applicable -> explain and do not apply.

### 3. Ask User When Needed

For **valid and large** or **uncertain** comments, use `vscode_askQuestions` with:
- quoted reviewer comment,
- analysis,
- proposed options (apply, skip, discuss).

Never silently skip comments.

### 4. Apply Changes

For each approved comment:

1. Read file before editing.
2. Make minimal, targeted fix only.
3. Avoid unrelated refactors or style-only edits.

### 5. Commit

After comments are processed, stage and commit with clear message:

```text
fix: {concise description}

{One line per addressed comment explaining what changed and why.}

Addresses PR review from {reviewer-name}.
```

- If issue linked to PR/branch, include prefix `fix(#{issue}): ...`.
- If multiple unrelated comment groups, use separate logical commits.
- Do not push unless user asks.

### 6. Resolve Threads as You Go

Resolve each review thread immediately after processing:
- Applied fix -> resolve.
- User-approved reject/skip with clear reasoning -> resolve.
- Invalid comment with explanation -> resolve.

Use `github-pull-request_resolveReviewThread` when:
- `canResolve` is `true`
- `isResolved` is `false`

Do not resolve threads user wants to defer.

### 7. Summarize

Report:
- applied comments,
- skipped/rejected comments with rationale,
- deferred comments,
- whether commits were made and commit hash,
- reminder to push when ready.

## Validation Checklist

Before applying any fix:

- [ ] Comment refers to code that still exists.
- [ ] Suggested fix is correct in project context.
- [ ] No behavior regression is introduced.
- [ ] Fix matches surrounding style.
- [ ] No security regression.

## Guidelines

- Be conservative: only apply changes you are confident are correct.
- Process one concern at a time.
- Investigate thoroughly before dismissing reviewer comments.
- Do not over-fix beyond reviewer scope.
- Give extra scrutiny to security-related comments.
- Commit messages in English.
