# Nexidion 4.3.2

This release makes Nexidion's content easier for AI agents to read accurately,
makes PDF ingestion reliable on small hosts, and fixes several privacy and
data-integrity bugs.

## Agent-native retrieval

- Full-text search can return verbatim snippets (`snippets=true`): exact passages
  from the current version with character offsets, heading path, version, the
  fields that matched, and a `summary_only` flag for hits found only through an
  AI summary. Search can be limited to a subtree, content kind, or authority.
- Node-scoped assets: `GET /nodes/<id>/assets` lists the images a node embeds;
  `GET /nodes/<id>/assets/<asset>` serves one (original or downscaled preview)
  under that node's access policy.
- Context bundles: `GET /nodes/<id>/context` returns a node's parent, children,
  outlinks, and backlinks, breadth-first and bounded, with relation, distance,
  link context, version, and summary status for every item. `GET
  /nodes/context-search` seeds the same expansion from search results. Hidden
  nodes are omitted without trace.

## PDF ingestion

- Optional background ingestion (`background=true`, used by the UI): the upload
  returns immediately and a worker thread in the app imports the file. The task
  runner can share the queue (`NEXIDION_INGEST_WORKER=off` leaves it to the runner).
- Runs record a heartbeat; runs abandoned by a stopped worker are retried once and
  then failed with an explanation.
- Each PDF is extracted once instead of twice.
- Chapter mode no longer drops pages before the first outline entry, and tolerates
  out-of-range or duplicate outline entries.
- `gunicorn.conf.py`: gthread worker with a 600-second timeout. The previous
  defaults (one sync worker, 30 seconds) killed long PDF uploads mid-import and
  blocked every other request meanwhile.

## Fixes

- Copying a node out of an AI-invisible or quarantined branch no longer makes the
  copy AI-readable.
- Vault export and import preserve access policies, content kind, authority,
  language, tags, and metadata; export timestamps are valid ISO 8601.
- AI actors can no longer fetch an asset by direct URL unless a node they may read
  embeds it.
- "Generate summary" no longer fails with an internal error.
- Deleting a user who uploaded files or requested summaries, imports, or tasks no
  longer fails.
- Task batches are all-or-nothing.
- Worker-completed summaries and PDF imports refresh the cached vault tree.
- The database driver is named explicitly (`postgresql+psycopg2`). SQLAlchemy 2.1
  maps a bare `postgresql://` URL to psycopg 3, which is not installed, so fresh
  images failed at startup.
- Malformed vault imports are rejected with a clear error; request bodies are
  capped at 128 MiB (`NEXIDION_MAX_UPLOAD_MB`).

## Database migration

Migration `b7d3e2a91c40` adds lifecycle columns to `ingestion_runs` (artifact,
stored request, attempts, start time, heartbeat). Runs still marked `processing`
more than 15 minutes after creation are marked failed as interrupted. The
downgrade removes the columns.

## Compatibility

Nexidion MCP 1.3.0 is the corresponding connector release; its new tools need the
4.3.2 endpoints. Deploy the application before the connector.
