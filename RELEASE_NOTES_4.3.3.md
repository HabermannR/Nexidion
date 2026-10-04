# Nexidion 4.3.3 — Targeted editing and navigation fixes

This maintenance release adds safe, targeted content editing and fixes navigation,
version history, managed images, and summary workflows.

## Targeted editing

- New `patch_node` API: replace exact text without resending an entire node.
  Expected versions and match counts prevent unintended changes; replacements
  are atomic and respect existing permissions, write locks, and protected sources.
- Preview changes with a dry-run diff. A changed patch creates exactly one new
  version; dry-runs and unchanged patches leave content and history untouched.
- The task runner uses the same patch service and records only saved changes.
  Summary-only refreshes use `set_summary` without creating content versions.

## Fixes and improvements

- Long version titles stay inside the sidebar, keeping the diff button visible.
- Deep breadcrumb paths collapse into an ancestor menu; all links use the active
  vault ID, fixing navigation to `/vaults/undefined/...`.
- Switching vaults clears stale selections and workspace state.
- Managed images load correctly when revisiting cached content.
- Copying AI summaries always includes node titles, UUIDs, and hierarchy.
- Summary generation chooses a configured provider instead of an unavailable
  local default; OpenRouter is supported in the provider selector.
- The admin dashboard shows the running application version and database revision.
- Remaining roadmap work is tracked in `TODO_4.4.md`.

## Compatibility and upgrade

- Nexidion MCP **1.4.0** exposes the new patch tool. Upgrade Nexidion before the
  connector; earlier connector tools remain available.
- No new database migration is introduced by 4.3.3.
- Docker images are published as `rhabermann/nexidion:v4.3.3` for Linux AMD64
  and ARM64. The same image runs the application and task runner.

## Validation

407 backend tests, 22 MCP tests, and 10 frontend tests passed. Frontend lint
and production build passed with existing warnings.
