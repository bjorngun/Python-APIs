---
name: plan-issue
description: "Create an implementation plan for a GitHub issue, with a local planning file and issue updates. Use when: planning work, creating a task breakdown, generating a plan for an issue, updating issue fields from an existing plan, following a plan, continuing with the next task, working on a specific task."
argument-hint: "Describe the work, say '/plan-issue 100', 'plan from this session', 'update issue 100 from plan', 'continue with the plan', 'start task N' or 'start phase N'"
---

# Implementation Planning (GitHub Issues)

Creates a structured implementation plan as a local file and updates the corresponding GitHub issue.
Supports creating a new plan, or updating issue metadata/body from an existing plan.

## Slash Command Parsing

- If the user invokes `/plan-issue <number>`, interpret `<number>` as a GitHub issue number in the
  current repository.
- Example: `/plan-issue 100` means issue `#100` in the current repository.
- If the user provides an owner/repo explicitly, use that repository; otherwise default to the
  current workspace repository.

## When to Use

- **Plan new work**: break down a feature/issue into phased tasks, create the plan file, and update
  the issue body/comments.
- **Plan from context**: review conversation or codebase context and generate the plan.
- **Update issue from plan**: sync an existing `.planning/` file into issue details.
- **Skip planning**: if the work is a single, self-contained task (one file, one concern), skip the
  plan and just do the work.

## Procedure

### Step 1: Gather Context

If the user says "from this session" or describes work inline, extract:
- What needs to change and why.
- Which files/areas are affected (search codebase if needed).
- Dependencies between changes.

If a GitHub issue exists, read it for title/body/labels/comments context.

### Step 2: Build the Task Breakdown

Break the work into **phases** and **tasks**.

**Phases**
- Group by shared context: tasks in a phase touch related files/concepts.
- Keep phases small: aim for **2-5 tasks per phase**.
- Order by dependency: earlier phases produce outputs later phases need.
- **Every plan ends with a Cleanup phase** (build/test, verify, changelog update, commit).

**Suggested phase pattern**

| Phase | Purpose | Typical Tasks |
|-------|---------|---------------|
| **0 - Setup** | Scaffolding, structural prep | Create files, registrations, models |
| **1-N - Core** | Main feature/refactor | Implementation by context |
| **N-1 - Polish** | Quality pass | Tests, edge cases, cleanup |
| **N - Cleanup** | Finalize for PR | Verify, update `CHANGELOG.md`, commit |

**Tasks**
- Short, action-oriented name (3-8 words).
- Each task includes: **What** (1-3 sentences), **Files** (created/modified),
  **Acceptance criteria**.
- Sequential numbering, 0-based.

### Step 3: Estimate Story Points

Assign a **story point estimate** from total task count and complexity.

| Story Points | Guideline |
|-------------|-----------|
| **1** | 1-2 tasks, trivial changes |
| **2** | 3-4 tasks, straightforward |
| **3** | 5-7 tasks, moderate complexity |
| **5** | 8-12 tasks, significant work |
| **8** | 13+ tasks, large scope (consider splitting) |

### Step 4: Pick Labels

Assign labels from this set (pick all that apply):

| Label | When |
|-------|------|
| `frontend` | Views, CSS, JS changes |
| `backend` | Services, models, APIs |
| `config` | Settings, feature flags |
| `bugfix` | Fixing a defect |
| `refactor` | Restructuring without behavior change |
| `ui-navigation` | Header/sidebar/routing |
| `infrastructure` | Build, deploy, CI/CD, tooling |

Add custom labels when needed. Keep labels lowercase and hyphenated.

### Step 5: Ask About Plan File

**Always ask the user** if they want a `.planning/` markdown file for this work.
- **Yes**: create a local tracking file with task details and completion notes.
- **No**: update GitHub issue only.

If the user declines, skip to Step 7.

### Step 6: Create the Plan File

Create `.planning/issue-{issue-number}-{short-name}.md`.

```markdown
# Issue #{Issue Number} - {Title}

> **Protocol**: Follow the `plan-issue` execution rules.
> **Created**: YYYY-MM-DD
> **Scope**: {One-sentence scope}
> **GitHub**: #{issue-number}

---

## Task Index

| Phase | # | Task | Details | Est. | Status |
|-------|---|------|---------|------|--------|
| **0 - {Name}** | 0 | {Task name} | [Details](#task-0-{slug}) | {est} | |

---

## Context

{Architecture notes, current behavior, goal, constraints, decisions}

---

## Phase 0 - {Name}

### Task 0: {Name}

**What:** {1-3 sentences}

**Files:**
- {file paths}

**Acceptance criteria:**
- {How to know it's done}

---

## Phase N - Cleanup

### Task N: Verify, test, update changelog, and commit

**What:** Run project verification commands. Update `CHANGELOG.md` with a concise entry for the completed plan. Review changes and commit.

**Files:**
- `CHANGELOG.md`
- (verification output only)

**Acceptance criteria:**
- Verification commands pass.
- `CHANGELOG.md` updated to reflect the completed work.
- All tasks marked `Done`.
- Committed with clear message linked to issue number.
```

### Step 7: Update GitHub Issue

Update issue using GitHub CLI and/or issue comment with:
- Labels from Step 4.
- Story point estimate (if project tracks points in issue body/template, add there).
- Condensed implementation plan.
- Total estimated effort.

If direct custom fields are unavailable in GitHub issues, post a structured planning comment and/or
append a "Plan" section to issue body.

### Step 8: Confirm

Report what was created:
- Plan file path (if created), else "Issue-only plan".
- Issue updates made (labels/body/comment).
- Total estimated effort.

## Update Mode

When user says "update issue X from plan" or "sync plan to issue":
1. Read existing `.planning/` file.
2. Extract task index, files list, and constraints.
3. Recalculate story points from task count.
4. Derive labels from affected files.
5. Build condensed implementation plan text.
6. Update GitHub issue labels/body/comment.

## Guidelines

- Plans live in `.planning/` and should be git-ignored working docs.
- The plan file is the authoritative tracker during execution.
- Do not over-plan very simple work.
- Keep issue plan summary concise.
- Ask user before creating a plan when scope is unclear.

## Executing a Plan

When user says "continue with the plan", "start task N", "start phase N", or "next task":

### Before Starting a Task

1. Read the plan file from `.planning/`.
2. Find next task not marked Done/Blocked.
3. Read task details.
4. Check for notes from previous tasks.

### During Execution

1. Mark task "In progress" in Task Index.
2. Stay in scope; add a new task for unrelated work.
3. Add notes for future tasks when needed.

### After Completing a Task

1. Mark task "Done" in Task Index.
2. Add completion note with key decisions and issues.
3. **Commit immediately after each completed task**:

```bash
git add -A
git commit -m "{type}(#${issue-number}): task {N} - short description"
```

### After Completing a Phase

1. Run project verification commands (tests/lint/build relevant to the repo).
2. Write a brief phase summary.
3. If this is the final cleanup phase, update `CHANGELOG.md` before committing.
4. Ensure all completed tasks are committed.

### Task Completion Checklist

Before marking any task Done:
- [ ] Verification commands pass
- [ ] Files touched listed in completion note
- [ ] Key decisions documented
- [ ] `CHANGELOG.md` updated (final cleanup task)
- [ ] **Changes committed immediately for this task**
