# Nexidion 4.3.1 Release Checklist

4.3.1 is a focused patch release restoring internal links and introducing
metadata-backed node access policies across the UI, API, task runner, and MCP.
Unrelated feature work is tracked in `TODO_4.3.2.md`.

## Node access policies

- [x] Add human write lock, AI write lock, AI invisibility, and quarantine metadata.
- [x] Enforce inherited restrictions while preserving explicit child quarantine
  when a parent is unquarantined.
- [x] Enforce policies for human users, the task runner, and MCP actors.
- [x] Preserve policy metadata during cross-vault subtree copies.
- [x] Add UI controls and policy-state icons.
- [x] Add service, API, and integration tests.
- [x] Audit every read route for AI-invisible and quarantine metadata leaks.
- [x] Verify policy behavior through clean local Nexidion and MCP containers.

## MCP identity and contract

- [x] Add a short-lived Nexidion actor-token exchange for stdio MCP.
- [x] Mark OAuth-bound HTTP MCP tokens with `actor_type=mcp`.
- [x] Forward quarantine opt-in on policy-sensitive tools.
- [x] Add committed MCP unit and integration tests.
- [x] Document the HTTP/stdio identity distinction and security boundary.
- [x] Version the MCP release as 1.2.0.

## Internal links package and regression fix

- [x] Correct the rehype-sanitize HAST property allowlist.
- [x] Add rendered frontend tests for title links, UUID links, and hostile labels.
- [x] Escape hostile display text in the Remark package.
- [x] Vendor the plugin as `packages/remark-internal-links`.
- [x] Make host, development Docker, and production Docker builds reproducible.
- [x] Remove obsolete tests, nested Git metadata, and IDE files from the package.

## Context selection UI

- [x] Remove unused saved context sets.
- [x] Allow individual selected context nodes to be removed.
- [x] Keep the compact context selector layout.

## Release preparation

- [x] Bump Nexidion to 4.3.1 and add release notes.
- [x] Run the full backend suite and record coverage.
- [x] Run frontend tests, lint, production build, and dependency audit.
- [x] Run internal package tests and dependency audit.
- [x] Run MCP tests from pinned dependencies.
- [x] Rehearse database upgrade and downgrade locally.
- [x] Build clean AMD64 Nexidion and MCP release candidates.
- [x] Smoke-test the release candidates together against a fresh local vault.
- [ ] Commit and push Nexidion and MCP master branches.
- [ ] Build and publish AMD64/ARM64 versioned Docker manifests.
- [ ] Record image digests and rollback commands before production deployment.

## Exit criteria

- [x] All new and existing tests pass with no unresolved high-severity audit issue.
- [x] Human and MCP integration coverage proves visibility and write-policy behavior.
- [x] Internal links render as real clickable anchors in the clean Docker image.
- [ ] Both release repositories are clean and tagged from reviewed commits.
- [x] Production deployment remains a separate, explicitly authorized operation.
