# Nexidion 4.3.1

This patch release restores clickable internal links and replaces icon-only AI
privacy conventions with enforceable node metadata policies.

## Included

- Human write lock, AI write lock, AI invisibility, and quarantine policies.
- Inherited subtree enforcement with sticky quarantine on descendants.
- Human, task-runner, delegated MCP, and service-user enforcement.
- Policy-aware trees, lists, content, versions, search, link resolution, task
  history, connector items, and provenance.
- Policy preservation during cross-vault subtree copies.
- Compact policy controls and visual confirmation in the node header and tree.
- Removal of unused saved context sets and individual context-node removal.
- Restored internal links after the 4.3.0 sanitizer regression.
- A vendored, tested `@nexidion/remark-internal-links` internal package.
- Short-lived MCP actor-token exchange for stdio clients.

## Database migration

Migration `4cb8a114f731` adds access-policy columns to `nodes`. Existing lock and
private icons are migrated to equivalent metadata policies. Vault tree caches are
invalidated and rebuilt automatically.

The downgrade removes the policy columns. Metadata policy choices made after the
upgrade are therefore not retained when downgrading.

## Compatibility

Nexidion MCP 1.2.0 is the corresponding policy-aware connector release. Older MCP
images must not be used for policy-sensitive access because stdio requests are not
marked as AI-mediated actors.

Production deployment is performed only from versioned, digest-pinned official
Docker images after a verified database and asset backup.
