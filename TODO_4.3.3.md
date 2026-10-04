# Nexidion 4.3.3 — minor release

4.3.3 is a small maintenance release: targeted editing and UI fixes plus the
already completed work listed below. All remaining feature, platform,
infrastructure, and release-quality work has moved to [TODO_4.4.md](TODO_4.4.md).
4.4 is the next major release in this roadmap.

Checked items describe the 4.3.3 source changes, not a production rollout.
Application 4.3.3 and MCP 1.4.0 are prepared for official Git and Docker releases.
The public MCP and Raspberry Pi still require a separately authorized deployment.

## Targeted editing and navigation

- [x] Add atomic literal `patch_node` to the backend and MCP, guarded by the current
  version and expected match counts, with dry-run diffs and existing access rules.
- [x] Route the taskrunner's `patch_node` through the same backend service. Return
  versions, diffs, and counts; reject conflicts and only audit actual saved changes.
- [x] Keep summary-only task actions working through `set_summary`, without content
  changes or new versions.
- [x] Keep long version titles within the sidebar and the diff button reachable.
- [x] Collapse deep breadcrumb paths behind an ancestor menu and truncate long labels; use the current vault ID for all ancestor links.

## Release-critical

### Copy AI summaries

- [x] Include each node's title and UUID in **Copy AI Summaries Only** output.
- [x] Preserve hierarchy and make the text format stable enough for machines as
  well as humans.

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
- [x] Fix default-provider selection: production currently reports `local` as the
  default even when no local LLM is configured; choose an available provider or
  require an explicit selection.

## Managed images and migration follow-up

- [x] Fix managed images after switching vaults; they currently appear broken
  until the page is refreshed.

## Vault switching and mobile UX

- [x] Clear or reconcile the selected node when switching vaults; switching while
  a node is selected can leave stale state and cause UI errors.
- [x] Add regression tests for vault switching with a selected node and for
  managed-image loading immediately after a switch, without requiring refresh.

## Cross-vault transfer

- [x] Support copying a node or complete subtree into another writable vault,
  creating new UUIDs and independent version histories.
- [x] Rewrite strong UUID links between nodes included in the same copy while
  leaving links to nodes outside the copied set explicit and unchanged.
- [x] Define managed-image, provenance, private-node, connector-managed source,
  and rollback behavior and cover them with API/service tests.

## Authentication roadmap

- [x] Create a skeletal Microsoft Entra ID / OpenID Connect proof of concept in
  the standalone
  `nexidion-auth-poc` project before integrating it into Nexidion.

## Portability, operations, and release quality

- [x] Harden and package `remark-internal-links` as an internal package before release:
  decide whether it remains a private workspace package or is published to npm;
  use an explicit package dependency instead of relying only on the Vite source
  alias; move `micromark-util-symbol` from `devDependencies` to `dependencies`;
  make clean `npm ci` and Docker builds work without committed plugin
  `node_modules`; and retain rendered frontend tests for weak title links and
  strong UUID links.

## Local verification

- [x] Complete backend regression suite: 407 tests passed, including node/API,
  access-policy, admin version reporting, and taskrunner coverage.
- [x] Taskrunner, stream diagnostics, and provider-config tests: 32 tests passed.
- [x] MCP repository suite: 22 tests passed.
- [x] Frontend tests: 10 tests passed, including breadcrumb navigation and vault changes; lint and production build passed with existing warnings.

Browser visual review and production deployment checks remain separate from the
release. Published image digests are verified locally before any production deploy.
