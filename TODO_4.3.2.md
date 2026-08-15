# Nexidion 4.3.2 Roadmap

This roadmap contains the feature and infrastructure work intentionally deferred
from the focused 4.3.1 security and link-restoration patch release.

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

- [x] Replace the built-in **Agent** chat interface with a small set of bounded,
  reviewable actions. Keep **Roll Up Branch Knowledge** as a first-class workflow and
  use the worker for queued execution; MCP remains the preferred interface for
  open-ended, conversational AI work.
- [x] Preserve the underlying task-runner and audit machinery. Treat it as the
  background worker for bounded actions, summaries, and ingestion rather than as
  a competing chat product.
- [x] Define and enforce roll-up semantics: selected nodes are destination roots;
  leaves stay unchanged; non-leaf notes and summaries are rewritten deepest
  first; each queued job has one exact allowed write target.
- [x] Preview every affected parent, allow exclusions, identify read-only
  connector-managed parents, and batch creation of large roll-up queues so the
  normal per-request task limiter does not truncate a branch.
- [x] Store an explicit provider/model on agent tasks and support local OpenAI-
  compatible, OpenAI, and OpenRouter execution without exposing credentials.
- [x] Add curated model selection: the three GPT-5.6 task models for OpenAI and
  at most ten cached, priced OpenRouter choices plus an explicit custom model.
- [x] Stream model responses into per-task diagnostic traces, separate inactivity
  and hard-turn timeouts, and make reasoning effort opt-in instead of forcing
  maximum reasoning.
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

## Cross-vault transfer

- [x] Support copying a node or complete subtree into another writable vault,
  creating new UUIDs and independent version histories.
- [x] Rewrite strong UUID links between nodes included in the same copy while
  leaving links to nodes outside the copied set explicit and unchanged.
- [x] Define managed-image, provenance, private-node, connector-managed source,
  and rollback behavior and cover them with API/service tests.
- [ ] Add the copy operation to the frontend. The backend endpoint and tests are
  present, but users cannot initiate a cross-vault copy from the tree yet.
- [ ] Add transactional **Move to another vault** only after copy behavior is
  proven. A move must preserve or explicitly redirect inbound links and must not
  be implemented as shared ownership.
- [ ] Do not introduce nodes owned by multiple vaults. Use vault access for shared
  libraries; consider read-only cross-vault mounts only as a separately designed
  future feature.

## Authentication roadmap

- [x] Create a skeletal Microsoft Entra ID / OpenID Connect proof of concept in
  the standalone
  `nexidion-auth-poc` project before integrating it into Nexidion.
- [ ] Test the now-private Entra proof of concept on the Windows work PC before
  deciding whether to integrate it.
- [ ] After the proof of concept, add external identities keyed by issuer and
  subject, just-in-time user provisioning, configurable tenant/domain policy,
  and a local emergency-admin login.
- [ ] Keep unrestricted self-registration disabled by default. Design invitation
  or approved-domain registration separately from enterprise SSO.

## Portability, operations, and release quality

- [x] Harden and package `remark-internal-links` as an internal package before release:
  decide whether it remains a private workspace package or is published to npm;
  use an explicit package dependency instead of relying only on the Vite source
  alias; move `micromark-util-symbol` from `devDependencies` to `dependencies`;
  make clean `npm ci` and Docker builds work without committed plugin
  `node_modules`; and retain rendered frontend tests for weak title links and
  strong UUID links.
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
