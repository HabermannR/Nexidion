# Nexidion 4.3.1 TODO

This release should harden the 4.3 ingestion architecture, close the known MCP
trust-boundary problem, and deliver the first non-PDF document connector.

## Release-critical

### Copy AI summaries

- [ ] Include each node's title and UUID in **Copy AI Summaries Only** output.
- [ ] Preserve hierarchy and make the text format stable enough for machines as
  well as humans.
- [ ] Add a backend endpoint so clients do not have to reconstruct the summary
  tree independently.
- [ ] Add an MCP tool for exporting/copying AI summaries, with options for vault,
  subtree, UUID inclusion, empty-summary handling, and hierarchy depth.
- [ ] Apply the same private-node and vault-permission rules as other tree APIs.
- [ ] Add UI, API, and MCP contract tests for titles, UUIDs, indentation, private
  nodes, and empty summaries.

### MCP security

- [ ] Remove `JWT_SECRET_KEY` from the MCP container.
- [ ] Replace locally minted Nexidion JWTs with a narrowly scoped server-to-server
  token exchange or delegated-token endpoint in Nexidion.
- [ ] Give MCP an explicit service identity with revocable credentials, scopes,
  audit attribution, rotation, and expiry; do not grant implicit administrator
  access.
- [ ] Keep remote OAuth calls bound to the human who authenticated, while stdio
  continues to use the dedicated `mcp` service account.
- [ ] Define tool scopes (read, write, summaries, tasks, ingestion, destructive)
  and enforce them in both Nexidion and MCP.
- [ ] Retain the HTTP prohibition on `delete_node`, or replace it with an explicit
  approval/capability mechanism.
- [ ] Validate OAuth redirect URIs strictly and review registration, PKCE, state,
  refresh-token rotation, replay protection, revocation, rate limiting, and login
  error handling.
- [ ] Add automated OAuth/MCP tests; the MCP repository currently has only a live
  self-test.
- [ ] Resolve or pin away the MCP SDK/Pydantic
  `IncompleteFieldDefinitionWarning` seen during production startup.
- [ ] Document secret rotation and an emergency MCP-token revocation procedure.

### Abaqus HTML import

- [ ] Inspect and document the supplied Abaqus HTML ZIP structure before fixing
  the connector contract.
- [ ] Implement an `abaqus-html` connector using the common connector registry,
  not a one-off import endpoint.
- [ ] Support ZIP upload through both the UI and REST API.
- [ ] Support the same three modes as PDF: **Import**, **Import and organize**, and
  **Organize only**.
- [ ] Preserve source hierarchy, anchors, tables, code/preformatted blocks,
  equations, internal links, images, and document-language metadata.
- [ ] Store source artifacts and managed images with complete provenance back to
  ZIP path, HTML file, section/anchor, and import run.
- [ ] Reject traversal paths, symlinks, oversized archives, decompression bombs,
  active content, remote resources, and unsafe HTML/SVG.
- [ ] Make re-import deterministic and define duplicate/update behavior.
- [ ] Add representative parser fixtures, security fixtures, API tests, and a
  restored-database migration/import rehearsal.

## Ingestion and connector platform

- [ ] Formalize the third-party connector/plugin interface: manifest, version,
  capabilities, configuration schema, credential references, health check, and
  lifecycle hooks.
- [ ] Decide how plugins are discovered and installed on Docker, Linux, and
  Windows without allowing arbitrary untrusted code by default.
- [ ] Add connector setup/edit/test/disable/remove controls in the UI.
- [ ] Add ingestion-run history, progress, structured errors, retry, cancellation,
  and dry-run/preview.
- [ ] Move large imports and AI organization to durable background jobs while
  retaining synchronous execution for small imports and API automation.
- [ ] Make task-runner ownership explicit: background ingestion/curation and agent
  tasks, not interactive MCP reads.
- [ ] Add idempotency keys and safe resume behavior for interrupted imports.
- [ ] Improve AI curation hierarchy quality: bounded 3–7 children where sensible,
  schema validation, retry/repair, maximum depth, and a single import root.
- [ ] Add SharePoint and generic wiki connectors after the plugin contract is
  stable; define read-only, ingest-only, and combined behavior for each.
- [ ] Expose connector registration, execution, and run status through MCP only
  after scoped MCP authorization exists.

## LLM and summaries

- [ ] Keep the built-in **Agent** tab out of the planned core product for now.
  Leave it documented as a possible future capability, but do not expand it in
  4.3.1; working through the Nexidion MCP server is the preferred interactive AI
  experience.
- [ ] Decide separately whether the remaining Agent tab and legacy task-runner UI
  should be hidden, removed, or retained as an experimental feature after MCP
  reaches feature parity. Do not let that decision block the 4.3.1 work.
- [ ] Restore explicit model selection for OpenAI and local OpenAI-compatible
  providers for summaries and AI-assisted imports instead of relying on
  hardcoded/default model names.
- [ ] Add provider model discovery where supported and a manual model field where
  it is not.
- [ ] Keep API keys and endpoint configuration in deployment/admin settings;
  model selectors may use configured providers but must not expose or store
  secrets.
- [ ] Store selected provider/model/prompt version on every curation and summary
  artifact.
- [ ] Fix default-provider selection: production currently reports `local` as the
  default even when no local LLM is configured; choose an available provider or
  require an explicit selection.
- [ ] Keep visual/vision processing optional and clearly show whether images will
  be sent to an external provider.
- [ ] Add cost/token estimates and confirmation for external-API organization of
  large documents.
- [ ] Support queued summary generation and visible progress/failure history.
- [ ] Improve stale-summary UX and provide bulk regenerate/clear operations.

## Managed images and migration follow-up

- [ ] Fix managed images after switching vaults; they currently appear broken
  until the page is refreshed.
- [ ] Visually verify the 15 converted assets in the production vault, including
  the four sanitized XHTML/SVG diagrams rasterized to PNG.
- [ ] Keep `secure_images` and both pre-4.3 backups until that review is complete;
  remove the legacy mount only in a separately rehearsed cleanup.
- [ ] Decide whether unreferenced legacy images should be imported into an asset
  library, archived, or left only in backup.
- [ ] Add thumbnails, asset metadata UI, missing-file diagnostics, and safe
  garbage collection for assets no longer referenced by any version or summary.
- [ ] Make legacy conversion transactional per node/import batch and emit a
  machine-readable report suitable for deployment automation.

## Vault switching and mobile UX

- [ ] Clear or reconcile the selected node when switching vaults; switching while
  a node is selected can leave stale state and cause UI errors.
- [ ] Improve vault switching on mobile so the control is easier to find and use
  in narrow layouts.
- [ ] Add regression tests for vault switching with a selected node and for
  managed-image loading immediately after a switch, without requiring refresh.

## Portability, operations, and release quality

- [ ] Add CI for backend tests, frontend lint/build/audit, migrations, MCP tests,
  and AMD64/ARM64 container builds.
- [ ] Add container health checks for Nexidion, task runner, MCP, and PostgreSQL;
  make deployments wait on health instead of container state alone.
- [ ] Run application containers as non-root users and review writable paths and
  read-only filesystem options.
- [ ] Reduce the Nexidion runtime image and startup time; avoid loading ONNX/PDF
  components for commands and services that do not need them.
- [ ] Suppress or resolve harmless ONNX GPU-discovery noise on CPU-only hosts.
- [ ] Split the oversized frontend bundle and retain reproducible `npm ci` builds.
- [ ] Add Python vulnerability auditing and dependency-update automation alongside
  the existing npm audit gate.
- [ ] Add tested Docker and bare-metal installation/upgrade instructions for Linux
  and Windows, including local-LLM networking examples.
- [ ] Automate pre-deployment PostgreSQL, managed-asset, configuration, and MCP
  state backups plus restore verification and digest-pinned rollback.
- [ ] Add a release checklist covering GitHub releases, Docker manifests/digests,
  migrations, conversion dry runs, Pi verification, and rollback evidence.

## API, MCP, and documentation consistency

- [ ] Publish an API contract for connectors, ingestion runs, summary artifacts,
  managed assets, and summary-only tree export.
- [ ] Bring MCP tools up to date with the 4.3 APIs instead of exposing only the
  older node/task surface.
- [ ] Document provenance fields and distinguish imported source nodes, human
  notes, AI synthesis nodes, summaries, and executor/requester identities.
- [ ] Update screenshots and user documentation after the Abaqus and connector
  setup UI stabilizes.
- [ ] Decide whether Nexidion's long-lived default branch should remain `master`;
  do not rename it as part of 4.3.1 unless CI, deployment, and documentation are
  updated together.

## Exit criteria

- [ ] All new backend, frontend, MCP, migration, and connector tests pass.
- [ ] npm and Python security audits have no unresolved high-severity findings.
- [ ] Docker images build and smoke-test on AMD64 and ARM64.
- [ ] Pure-metal smoke tests pass on Linux and Windows.
- [ ] Upgrade, Abaqus import, and rollback are rehearsed against a restored copy of
  the Raspberry Pi vault before production deployment.
- [ ] No legacy-image cleanup or MCP secret rotation occurs without a fresh,
  checksum-verified, off-device backup.
