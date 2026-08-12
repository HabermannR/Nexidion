# Connector and ingestion system

Nexidion loads built-in connectors and Python packages registered in the
`nexidion.connectors` entry-point group. A connector only discovers and normalizes
source documents; Nexidion owns authorization, hashing, versioning, provenance and
the frozen/managed-source policy.

Modes are `read`, `ingest`, and `both`. External write-back is a distinct capability
and is never implied by `both`. Credentials are not stored in connector configuration;
`credential_ref` identifies an environment variable or external secret-store entry.

The built-in deterministic PDF connector stores canonical extracted Markdown. Agent
summaries and restructuring should be performed later as derived knowledge.

## PDF HTTP API

The browser uses the same multipart endpoint available to API clients:

```text
POST /api/connectors/pdf/ingest
Authorization: Bearer <token>
Content-Type: multipart/form-data

vault_id=<integer>             required
file=@manual.pdf               required, maximum 100 MiB
parent_id=<node UUID>          optional
policy=managed                 optional
mode=extract                   extract | extract_and_curate | curate_only
granularity=auto               auto | document | chapter | page
provider=local                 local | openai (AI modes)
model=<model name>             optional (AI modes)
visual_mode=off                off | auto | all (AI modes)
```

`extract` completes deterministic extraction synchronously and returns HTTP 201 with
the ingestion run. With `auto`, a PDF outline produces chapter nodes; a PDF without
an outline produces page nodes. Re-uploading identical bytes under the same filename
is idempotent, while changed bytes update existing canonical nodes as new versions.

Every deterministic PDF import creates one stable managed document container. Page,
chapter, or whole-document canonical nodes are children of that container. In
`extract_and_curate` mode, the AI synthesis root is also created beneath the same
container, so a PDF never scatters imported or derived nodes across the vault root.

`extract_and_curate` creates those canonical nodes and queues additional AI synthesis
nodes. `curate_only` stores the PDF and page extraction as an internal source artifact
but creates no mechanical nodes. Both AI modes return HTTP 202 and a `curation_job`.
Generated nodes carry provider/model/prompt metadata and page-level provenance links
to the exact source artifact revision.

Raster images found in PDFs are stored as vault-scoped managed assets and embedded in
the extracted Markdown. When PyMuPDF reports an omitted graphic but provides no
extractable raster image, Nexidion replaces the cryptic parser marker with a readable
page-specific omission note.

Inspect provenance and execution history with:

```text
GET /api/connectors?vault_id=<vault ID>
GET /api/connectors/<connector ID>/runs
GET /api/connectors/runs/<run ID>
GET /api/connectors/<connector ID>/items
GET /api/connectors/curation-jobs/<job ID>
```

The original `POST /api/vaults/<vault ID>/ingest/pdf` URL remains as a compatibility
alias and returns the same completed-run representation.

## Portable commands

All commands below are identical on Linux, Windows PowerShell, Windows Command Prompt,
and inside the application container (activate the virtual environment first when not
using Docker):

```text
flask list-connectors
flask register-connector VAULT_ID pdf NAME --user-id USER_ID --config-json CONFIG
flask run-ingestion CONNECTOR_UUID --user-id USER_ID --executor-id AGENT_USER_ID
python task_runner.py
```

Example PDF configuration JSON:

```json
{"path":"C:/Documents/manual.pdf","policy":"managed","parent_id":null}
```

Use forward slashes or correctly escaped backslashes in JSON on Windows. Docker paths
refer to paths mounted inside the container, not host paths.

Run the web application with `python serve.py` on Windows or bare metal. Linux may use
the same command; production Docker continues to use Gunicorn.

Third-party packages expose a connector factory in `pyproject.toml`:

```toml
[project.entry-points."nexidion.connectors"]
sharepoint = "my_package.sharepoint:SharePointConnector"
```
