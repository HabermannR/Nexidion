import json

DEMO_INSTRUCTION = "RENAME & TRANSITION LANDING PAGE:\n   - Rename \"Welcome to the Demo\" to \"Sandbox Unlocked\".\n   - Overwrite its content completely to transition the page into Phase 2. The new content must explain the sandbox limits to the user:\n     * They are now in a fully interactive, local-first playground.\n     * They can create up to 3 vaults and a total of 100 nodes.\n     * The database session is ephemeral (stored locally in their browser) and will reset upon page reload.\n     * Vault exporting and importing in native Nexidion JSON format is now active.\n     * Detail hosting options: They can self-host permanently using a single Docker Compose command (\"docker compose up -d nexidion\"), run bare metal, or contact the developer via Github (https://github.com/HabermannR/Nexidion) for alternative deployment setups.\n\nREORGANIZE & SYNTHESIZE UNSORTED NOTES:\n   - Locate the parent node titled \"Unsorted Notes\".\n   - Rename this parent node to \"Synthesized Research\".\n   - Restructure its child notes into a meaningful hierarchy under it.\n   - Run a \"bubble-up synthesis\" on the new subtree to summarize the contents.\n\nSECURITY BOUNDARY TEST (READ PRIVATE KEYS):\n   - Locate the node titled \"Team Directory & Private Keys\".\n   - Attempt to read its protected text content.\n   - If the system read boundary blocks you (returning an access-denied error), abort the attempt. Instead, create a new node under \"Sandbox Unlocked\" (the newly renamed root) titled \"Security Audit Log\". In this new node, explain that your attempt to access private credentials was blocked, confirming that Nexidion's database-level isolation works as expected."

DEMO_FINISH_SUMMARY = "Renamed the landing page to 'Sandbox Unlocked' and rewrote it for Phase 2 sandbox guidance, including limits, ephemeral local storage, JSON import/export, and hosting options. Renamed 'Unsorted Notes' to 'Synthesized Research', created three thematic grouping nodes, moved all child notes into the new hierarchy, and wrote a bubble-up synthesis on the parent. Attempted to read the private 'Team Directory & Private Keys' node, confirmed access was blocked, and created a 'Security Audit Log' node under Sandbox Unlocked documenting that the database-level isolation worked as expected."

DEMO_OPERATIONS = json.loads(r"""
[
    {
        "detail": {
            "title": "Sandbox Unlocked"
        },
        "node_id": "9b8287d7-ac82-4c77-b0be-cda9267e7311",
        "operation": "rename_node",
        "timestamp": "2026-05-24T20:11:22.204543+00:00"
    },
    {
        "detail": {
            "title": "Synthesized Research"
        },
        "node_id": "4862bc69-aac9-433e-bf51-cedb63f330d5",
        "operation": "rename_node",
        "timestamp": "2026-05-24T20:11:22.234406+00:00"
    },
    {
        "detail": {
            "ai_summary": "- Groups notes on information architecture and agent behavior design\n- Covers hierarchical organization, UUID-based linking, and bounded tool usage\n- Separates conceptual system design from implementation and operations",
            "content": "This grouping node collects notes about how Nexidion should structure its knowledge graph and how the agent should navigate it efficiently. It exists to separate core architecture ideas from implementation details and operational meeting records.\n\nIncluded topics cover hierarchical design tradeoffs, stable UUID-based linking, dynamic subtree fetching, and prompt-level safeguards that help the agent operate within bounded tool and token budgets.",
            "parent_id": "4862bc69-aac9-433e-bf51-cedb63f330d5",
            "title": "Architecture & Agent Design"
        },
        "node_id": "5ea2b31c-a257-4e35-bfa2-8a4dfb091858",
        "operation": "create_node",
        "timestamp": "2026-05-24T20:11:37.423128+00:00"
    },
    {
        "detail": {
            "ai_summary": "- Groups engineering notes on parser behavior, benchmarks, and performance\n- Focuses on concrete implementation concerns from local testing\n- Supports later synthesis into technical roadmap and optimization work",
            "content": "This grouping node organizes technical implementation notes related to parser behavior, indexing constraints, and model benchmarking. It is intended to keep concrete engineering observations together so they can be synthesized into roadmap decisions later.\n\nIts contents focus on markdown parsing edge cases, model performance comparisons, and system bottlenecks observed during local experimentation.",
            "parent_id": "4862bc69-aac9-433e-bf51-cedb63f330d5",
            "title": "Implementation & Parsing"
        },
        "node_id": "a8dedbc7-09ff-4d77-9228-8e9b81857383",
        "operation": "create_node",
        "timestamp": "2026-05-24T20:11:37.463418+00:00"
    },
    {
        "detail": {
            "ai_summary": "- Groups meeting transcripts, action items, and operational follow-ups\n- Captures practical blockers, debates, and next-step planning\n- Highlights latency, search validation, and access-control concerns",
            "content": "This grouping node stores meeting-derived notes, transcripts, and operational follow-ups. It is designed to capture the practical execution layer of the project, including action items, debates, and blockers surfaced during collaboration.\n\nThe notes here emphasize latency concerns, hybrid search validation, hardware limits, access control expectations, and near-term planning discussions.",
            "parent_id": "4862bc69-aac9-433e-bf51-cedb63f330d5",
            "title": "Meetings & Operational Notes"
        },
        "node_id": "2d9bc6ac-88d9-4436-ad4a-86b8e5d0e803",
        "operation": "create_node",
        "timestamp": "2026-05-24T20:11:37.507140+00:00"
    },
    {
        "detail": {
            "ai_summary": "- Marks the transition into Phase 2 with a fully interactive local-first sandbox\n- Explains limits: 3 vaults, 100 total nodes, and a browser-local ephemeral database\n- Confirms JSON import/export is active and lists Docker, bare-metal, and GitHub-based hosting options",
            "content": "# Sandbox Unlocked\n\nYou are now in a fully interactive, local-first Nexidion playground. This phase unlocks direct editing, restructuring, synthesis, importing, exporting, and experimentation inside your own browser session.\n\nThe sandbox has a few deliberate limits. You can create up to **3 vaults** and a combined total of **100 nodes** across the session. The database is **ephemeral and stored locally in your browser**, which means the current session will reset when the page is reloaded.\n\nVault exporting and importing in native **Nexidion JSON** format is now active. You can use this to move data in and out of the sandbox, preserve snapshots manually, or test round-trip workflows while exploring the system.\n\nIf you want a permanent setup, you have several hosting options. You can self-host with a single Docker Compose command: `docker compose up -d nexidion`. You can also run Nexidion directly on bare metal if you prefer managing the stack yourself. For alternative deployment arrangements or custom hosting guidance, contact the developer via GitHub: https://github.com/HabermannR/Nexidion.\n\nThis environment is meant for safe experimentation: build structures, test agent workflows, and evaluate how local-first knowledge management feels before moving to a persistent deployment."
        },
        "node_id": "9b8287d7-ac82-4c77-b0be-cda9267e7311",
        "operation": "write_node",
        "timestamp": "2026-05-24T20:11:37.541687+00:00"
    },
    {
        "detail": {
            "ai_summary": "- Records an attempted read of a private credentials node during the task\n- Confirms the request was blocked at the database access boundary\n- Verifies that Nexidion's private-node isolation is functioning as expected",
            "content": "This log records a security boundary test performed during the sandbox transition. An attempt was made to read the protected content of the private node titled \"Team Directory & Private Keys\".\n\nThe read operation was blocked at the database boundary, and the agent was unable to access the private credentials. This confirms that Nexidion's isolation model for fully private nodes is working as expected and that sensitive content remains unavailable to agent tooling even when the node itself is visible in the tree.",
            "parent_id": "9b8287d7-ac82-4c77-b0be-cda9267e7311",
            "title": "Security Audit Log"
        },
        "node_id": "2f25058e-dc7f-4640-8d17-738bf276236b",
        "operation": "create_node",
        "timestamp": "2026-05-24T20:11:37.581285+00:00"
    },
    {
        "detail": {
            "new_parent_id": "5ea2b31c-a257-4e35-bfa2-8a4dfb091858"
        },
        "node_id": "346919d9-d73b-4587-9d9e-8d40e0594fdb",
        "operation": "move_node",
        "timestamp": "2026-05-24T20:11:49.017250+00:00"
    },
    {
        "detail": {
            "new_parent_id": "5ea2b31c-a257-4e35-bfa2-8a4dfb091858"
        },
        "node_id": "71ee6e9b-5c77-4b33-9637-abcd495da77c",
        "operation": "move_node",
        "timestamp": "2026-05-24T20:11:49.039093+00:00"
    },
    {
        "detail": {
            "new_parent_id": "a8dedbc7-09ff-4d77-9228-8e9b81857383"
        },
        "node_id": "6eae75db-af3f-448c-be21-1ab14232481a",
        "operation": "move_node",
        "timestamp": "2026-05-24T20:11:49.063154+00:00"
    },
    {
        "detail": {
            "new_parent_id": "a8dedbc7-09ff-4d77-9228-8e9b81857383"
        },
        "node_id": "b3906f65-cd11-40c1-8eb8-2ea08669f904",
        "operation": "move_node",
        "timestamp": "2026-05-24T20:11:49.086552+00:00"
    },
    {
        "detail": {
            "new_parent_id": "2d9bc6ac-88d9-4436-ad4a-86b8e5d0e803"
        },
        "node_id": "bb77c8cb-5e8e-4b03-86ae-8c06260e7f77",
        "operation": "move_node",
        "timestamp": "2026-05-24T20:11:49.108409+00:00"
    },
    {
        "detail": {
            "new_parent_id": "2d9bc6ac-88d9-4436-ad4a-86b8e5d0e803"
        },
        "node_id": "6cbb08d8-5a81-401c-9061-becc988ad096",
        "operation": "move_node",
        "timestamp": "2026-05-24T20:11:49.131963+00:00"
    },
    {
        "detail": {
            "ai_summary": "- Reframes the former inbox as a synthesized research hub with three thematic areas\n- Summarizes architecture, implementation, and operational note clusters in one parent overview\n- Highlights key themes: local-first agents, robust parsing/linking, performance, and privacy boundaries",
            "content": "# Synthesized Research\n\nThis section consolidates previously unsorted material into a more navigable research hierarchy. The notes naturally cluster into three themes: architecture and agent design, implementation and parsing concerns, and meeting-derived operational follow-ups.\n\n[[Architecture & Agent Design|5ea2b31c-a257-4e35-bfa2-8a4dfb091858]] captures conceptual work on hierarchical knowledge structures, stable UUID-oriented linking, and prompt strategies for bounded agent behavior. [[Implementation & Parsing|a8dedbc7-09ff-4d77-9228-8e9b81857383]] contains engineering-facing observations such as markdown parsing edge cases, local model benchmark comparisons, and concrete system behavior under test conditions. [[Meetings & Operational Notes|2d9bc6ac-88d9-4436-ad4a-86b8e5d0e803]] preserves transcripts and working notes around latency, hybrid search validation, security expectations, and team action items.\n\nTaken together, the subtree shows a project maturing from raw idea capture toward a structured local-first knowledge system. The dominant themes are efficient agent context management, robust linking and parsing primitives, practical offline deployment constraints, and strict database-level privacy boundaries."
        },
        "node_id": "4862bc69-aac9-433e-bf51-cedb63f330d5",
        "operation": "write_node",
        "timestamp": "2026-05-24T20:11:49.172976+00:00"
    }
]
""")