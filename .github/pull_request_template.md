# Pull Request

## Summary

Describe what changed and why.

## Linked Issue

- GitHub issue: #ISSUE_NUMBER

## Planning

- [ ] I used `/plan-issue <number>` for this work.
- [ ] If I did not use `/plan-issue`, I confirm this was a small self-contained change.

## SemVer Impact

Select exactly one:

- [ ] `semver:major` (breaking change)
- [ ] `semver:minor` (backward-compatible feature)
- [ ] `semver:none` (no release impact)

### How to classify

Pick `semver:major` if **any** of these breaking-change signals apply:

- Removed or renamed a public name (function, class, method, attribute, or `__all__` export).
- Changed a function/method signature (parameters, ordering, required vs. optional) or its
  return type/shape.
- Removed or altered legacy-compatible behavior that callers may rely on.
- Changed a default value, raised exception type, or other observable runtime behavior.

Otherwise:

- Use `semver:minor` for **purely additive**, backward-compatible features.
- Use `semver:none` for docs, chores, tests, CI, or internal-only changes with no release impact.

When in doubt about compatibility, default to `semver:major` and call it out in the PR.

- [ ] My selected label matches the
  [Versioning and Release Flow](https://github.com/bjorngun/Python-APIs/blob/main/README.md#versioning-and-release-flow)
  policy.

## Task-Bounded Commits (for planned work)

- [ ] I committed changes after each completed planned task.
- [ ] Commit messages include issue number and task context.

Example commit message:

```text
feat(#123): task 2 - add membership paging contract
```

## Validation

- [ ] Tests pass locally.
- [ ] Linting passes locally.
- [ ] Documentation/instructions were updated if behavior changed.

## Notes

Add migration notes, rollout risks, or follow-up items here.
