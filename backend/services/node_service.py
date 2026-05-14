# backend/services/node_service.py

from typing import List, Dict, Any, Optional, Set
from sqlalchemy.orm import joinedload, with_parent, defer
from sqlalchemy import func, select, or_, case, cast, Float
import hashlib
import json
import re

# Importiere die Services und Modelle
from .vault_service import _verify_vault_access
from ..models import db, Node, Version, Vault, User

DEFAULT_NODE_ICON = "bxs-file-doc"
icon_groups: List[Dict[str, Any]] = [
    {
        "title": "Ordner & Container",
        "icons": [
            {"id": "bxs-folder", "name": "Ordner"},
            {"id": "bx-folder-open", "name": "Offener Ordner"},
            {"id": "bxs-inbox", "name": "Eingang"},
            {"id": "bxs-archive", "name": "Archiv"},
            {"id": "bxs-box", "name": "Sammlung"},
            {"id": "bxs-component", "name": "Baustein"},
        ],
    },
    {
        "title": "Dokumente & Notizen",
        "icons": [
            {"id": "bxs-file-doc", "name": "Dokument"},
            {"id": "bxs-note", "name": "Notiz"},
            {"id": "bx-code-block", "name": "Code"},
            {"id": "bxs-file-pdf", "name": "PDF"},
            {"id": "bxs-copy-alt", "name": "Vorlage"},
            {"id": "bxs-edit-alt", "name": "Entwurf"},
        ],
    },
    {
        "title": "Konzepte & Planung",
        "icons": [
            {"id": "bxs-bulb", "name": "Idee"},
            {"id": "bxs-brain", "name": "Konzept"},
            {"id": "bx-sitemap", "name": "Struktur"},
            {"id": "bxs-bullseye", "name": "Ziel"},
            {"id": "bxs-flag-alt", "name": "Meilenstein"},
            {"id": "bxs-network-chart", "name": "Beziehungen"},
        ],
    },
    {
        "title": "Personen & Teams",
        "icons": [
            {"id": "bxs-user", "name": "Person"},
            {"id": "bxs-group", "name": "Team"},
            {"id": "bxs-contact", "name": "Kontakt"},
            {"id": "bxs-user-detail", "name": "Profil"},
            {"id": "bxs-user-voice", "name": "Feedback"},
            {"id": "bxs-user-plus", "name": "Benutzer hinzufügen"},
        ],
    },
    {
        "title": "Listen & Aufgaben",
        "icons": [
            {"id": "bx-list-ul", "name": "Liste"},
            {"id": "bx-check-square", "name": "Aufgabe"},
            {"id": "bxs-hourglass-top", "name": "In Bearbeitung"},
            {"id": "bxs-calendar", "name": "Termin"},
            {"id": "bxs-time-five", "name": "Frist"},
            {"id": "bxs-calendar-check", "name": "Abgeschlossen"},
            {"id": "bxs-calendar-x", "name": "Verpasst"},
        ],
    },
    {
        "title": "Struktur & Metadaten",
        "icons": [
            {"id": "bxs-tag-alt", "name": "Schlagwort"},
            {"id": "bx-link", "name": "Link"},
            {"id": "bx-link-external", "name": "Externer Link"},
            {"id": "bxs-pin", "name": "Angepinnt"},
            {"id": "bxs-star", "name": "Favorit"},
            {"id": "bxs-bookmark", "name": "Lesezeichen"},
            {"id": "bxs-bookmark-star", "name": "Favoriten-Lesezeichen"},
        ],
    },
    {
        "title": "Medien & Anhänge",
        "icons": [
            {"id": "bxs-image-alt", "name": "Bild"},
            {"id": "bxs-video", "name": "Video"},
            {"id": "bxs-music", "name": "Audio"},
            {"id": "bxs-file-archive", "name": "ZIP-Archiv"},
            {"id": "bxs-cloud-upload", "name": "Upload"},
            {"id": "bxs-file-find", "name": "Dateisuche"},
        ],
    },
    {
        "title": "Daten & Visualisierung",
        "icons": [
            {"id": "bx-table", "name": "Tabelle"},
            {"id": "bxs-bar-chart-alt-2", "name": "Balkendiagramm"},
            {"id": "bxs-pie-chart-alt-2", "name": "Kreisdiagramm"},
            {"id": "bxs-data", "name": "Datenquelle"},
            {"id": "bxs-map", "name": "Karte"},
            {"id": "bxs-map-pin", "name": "Ort"},
        ],
    },
    {
        "title": "Status & Kommunikation",
        "icons": [
            {"id": "bxs-info-circle", "name": "Info"},
            {"id": "bxs-help-circle", "name": "Frage"},
            {"id": "bxs-error-circle", "name": "Warnung"},
            {"id": "bxs-check-circle", "name": "Bestätigt"},
            {"id": "bxs-comment-detail", "name": "Diskussion"},
            {"id": "bxs-bell", "name": "Benachrichtigung"},
            {"id": "bxs-lock-alt", "name": "Gesperrt / Privat"},
            {"id": "bx-trash", "name": "Papierkorb"},
        ],
    },
]

# Das Set der erlaubten Icons wird dynamisch aus der obigen Liste generiert.
# Dies verhindert Inkonsistenzen und erleichtert die Wartung.
ALLOWED_ICONS: Set[str] = {
    icon["id"]
    for group in icon_groups
    for icon in group["icons"]
}

# ========================================================================
# PRIVATE HELPER FUNCTIONS
# ========================================================================

def _is_descendant(ancestor_id: str, descendant_id: str, vault_id: int) -> bool:
    """Prüft, ob ein Node ein Nachkomme eines anderen ist, um Zyklen zu verhindern."""
    if not descendant_id or not ancestor_id:
        return False
    # Rekursive CTE (Common Table Expression) zur Ermittlung aller Vorfahren
    cte = db.session.query(Node.id, Node.parent_id).filter(Node.id == descendant_id, Node.vault_id == vault_id).cte(
        name="ancestors", recursive=True)
    parent_alias, cte_alias = db.aliased(Node), db.aliased(cte, name="cte_alias")
    cte = cte.union_all(
        db.session.query(parent_alias.id, parent_alias.parent_id).filter(parent_alias.vault_id == vault_id).join(
            cte_alias, parent_alias.id == cte_alias.c.parent_id))
    # Prüfen, ob der potentielle Vorfahre in der Ahnentafel vorkommt
    return db.session.query(cte.c.id).filter(cte.c.id == ancestor_id).scalar() is not None


def _get_nodes_by_ids_and_verify_access(node_ids: list[str], vault_id: int, user_id: int) -> List[Node]:
    """
    Zentrale, strikte Hilfsfunktion: Holt eine Liste von Nodes anhand ihrer IDs, lädt
    deren aktuelle Versionen und Autoren effizient vor und validiert den Zugriff.

    Löst einen Fehler aus, wenn ein Node nicht gefunden wird oder die Berechtigung fehlt.
    """
    # Schritt 1: Allgemeine Vault-Berechtigung prüfen
    _verify_vault_access(vault_id, user_id)
    if not node_ids:
        return []

    # Schritt 2: Alle angeforderten Nodes und zugehörige Daten effizient laden.
    nodes = (
        Node.query
        .options(
            # Lade die aktuelle Version und dessen Autor mit einem einzigen Join.
            joinedload(Node.current_version_object).joinedload(Version.author)
        )
        .filter(Node.id.in_(node_ids))
        .all()
    )

    # Schritt 3: Strikte "Alles-oder-nichts"-Validierung
    found_nodes_map = {node.id: node for node in nodes}
    requested_ids_set = set(node_ids)

    # Prüfen, ob alle angeforderten IDs überhaupt existieren
    if len(found_nodes_map) != len(requested_ids_set):
        missing_ids = requested_ids_set - found_nodes_map.keys()
        raise ValueError(f"Node(s) with ID(s) not found: {', '.join(missing_ids)}")

    # Prüfen, ob alle existierenden Nodes zum richtigen Vault gehören
    for node in nodes:
        if node.vault_id != vault_id:
            raise PermissionError(f"Permission denied to access node with ID: {node.id}")

    # Schritt 4: Wenn alle Prüfungen bestanden wurden, die Liste der Nodes zurückgeben
    return nodes


def rebuild_vault_tree_cache(vault_id: int) -> dict:
    """Builds and caches both the UI tree and Agent tree in a single pass."""

    # 1. Fetch nodes (Optimized: ignoring content and search vectors)
    nodes = (
        Node.query
        .options(
            joinedload(Node.current_version_object)
            .defer(Version.content)
            .defer(Version.fts_en)
            .defer(Version.fts_de),
            defer(Node.fts_summary_en),
            defer(Node.fts_summary_de)
        )
        .filter_by(vault_id=vault_id)
        .all()
    )
    ui_node_map = {}
    agent_node_map = {}

    # 2. Build flat dictionaries
    for n in nodes:
        title = n.current_version_object.title if n.current_version_object else "Unbenannter Node"
        ui_node_map[n.id] = {
            'id': n.id,
            'title': title,
            'parent_id': n.parent_id,
            'icon': n.icon,
            'children': []
        }
        agent_node_map[n.id] = {
            'id': n.id,
            'title': title,
            'parent_id': n.parent_id,
            'ai_summary': n.ai_summary,
            'summary_is_current': n.summary_is_current,
            'children': []
        }

    # 3. Link children to parents
    ui_roots = []
    agent_roots = []
    for node in nodes:
        ui_d = ui_node_map[node.id]
        agent_d = agent_node_map[node.id]
        if node.parent_id and node.parent_id in ui_node_map:
            ui_node_map[node.parent_id]['children'].append(ui_d)
            agent_node_map[node.parent_id]['children'].append(agent_d)
        else:
            ui_roots.append(ui_d)
            agent_roots.append(agent_d)

    # 4. Sort trees alphabetically
    def sort_tree(nodes_list):
        nodes_list.sort(key=lambda n: n.get('title') or '')
        for n in nodes_list:
            sort_tree(n['children'])

    sort_tree(ui_roots)
    sort_tree(agent_roots)

    # 5. Generate ETags
    ui_etag = hashlib.md5(json.dumps(ui_roots, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    agent_etag = hashlib.md5(json.dumps(agent_roots, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


    vault = db.session.get(Vault, vault_id)
    if vault:
        vault.cached_ui_tree = ui_roots
        vault.cached_ui_tree_etag = ui_etag
        vault.cached_agent_tree = agent_roots
        vault.cached_agent_tree_etag = agent_etag
        db.session.commit()

    return {
        'ui': (ui_roots, ui_etag),
        'agent': (agent_roots, agent_etag)
    }


def get_nodes_as_tree(vault_id: int, user_id: int, format_type: str = 'tree', client_etag: Optional[str] = None):
    _verify_vault_access(vault_id, user_id)
    vault = db.session.get(Vault, vault_id)
    if not vault:
        raise ValueError("Vault not found.")
    is_ui = (format_type == 'tree')
    target_etag = vault.cached_ui_tree_etag if is_ui else vault.cached_agent_tree_etag
    if target_etag and client_etag == target_etag:
        return None, target_etag, True
    target_tree = vault.cached_ui_tree if is_ui else vault.cached_agent_tree
    if not target_tree:
        trees = rebuild_vault_tree_cache(vault_id)
        target_tree, target_etag = trees['ui'] if is_ui else trees['agent']
    return target_tree, target_etag, False


def get_nodes_as_list(vault_id: int, user_id: int, v3_mode: bool = False) -> list[dict]:
    _verify_vault_access(vault_id, user_id)
    nodes = (
        Node.query
        .options(joinedload(Node.current_version_object))
        .filter_by(vault_id=vault_id)
        .join(Node.current_version_object)
        .order_by(Version.title)
        .all()
    )
    return [node.to_dict(include_content=True) for node in nodes]


def find_node_by_title(title: str, vault_id: int, user_id: int) -> dict | None:
    _verify_vault_access(vault_id, user_id)
    if not title or not title.strip():
        raise ValueError("Search title cannot be empty")
    search_term = f"%{title}%"
    relevance = case((Version.title.ilike(title), 0), else_=1)
    subquery = (
        select(Version.node_id)
        .join(Node, Version.node_id == Node.id)
        .filter(
            Node.vault_id == vault_id,
            Version.title.ilike(search_term),
            Node.current_version == Version.version
        )
        .order_by(relevance, Version.title)
        .limit(1)
        .scalar_subquery()
    )
    node = Node.query.options(joinedload(Node.current_version_object)).filter(Node.id == subquery).first()
    return node.to_dict(include_content=True) if node else None


def search_nodes_fulltext(query: str, vault_id: int, user_id: int, limit: int = 20) -> list[dict]:
    _verify_vault_access(vault_id, user_id)
    if not query or not query.strip():
        return []
    q = query.strip()
    tsquery_en = func.plainto_tsquery("english", q)
    tsquery_de = func.plainto_tsquery("german", q)
    combined_en = Version.fts_en.op("||")(Node.fts_summary_en)
    combined_de = Version.fts_de.op("||")(Node.fts_summary_de)
    title_length_bonus = case(
        (func.lower(Version.title) == q.lower(), 1.0),
        (Version.title.ilike(f"%{q}%"),
         cast(func.length(q), Float) / func.nullif(func.length(Version.title), 0)),
        else_=0.0
    )
    relevance = (
            func.ts_rank(combined_en, tsquery_en) +
            func.ts_rank(combined_de, tsquery_de) +
            title_length_bonus
    ).label("relevance")
    nodes = (
        db.session.query(Node, relevance)
        .join(Node.current_version_object)
        .filter(
            Node.vault_id == vault_id,
            or_(
                Version.fts_en.op("@@")(tsquery_en),
                Version.fts_de.op("@@")(tsquery_de),
                Node.fts_summary_en.op("@@")(tsquery_en),
                Node.fts_summary_de.op("@@")(tsquery_de),
            )
        )
        .order_by(relevance.desc())
        .limit(limit)
        .all()
    )
    return [
        {**node.to_dict(), "relevance_score": float(score)}
        for node, score in nodes
    ]


def get_node_by_id(node_id: str, vault_id: int, user_id: int, target_version: Optional[int] = None,
                   v3_mode: bool = False) -> dict | None:
    """Holt einen einzelnen Node nach ID, schnell und ohne Versionsverlauf."""
    _verify_vault_access(vault_id, user_id)
    node = (
        Node.query
        .options(joinedload(Node.current_version_object))
        .filter_by(id=node_id, vault_id=vault_id)
        .first()
    )
    if not node:
        return None

    node_dict = node.to_dict(include_content=True)

    # +++ NEU: Überschreibe den Payload, wenn eine spezifische Version angefragt wurde +++
    if target_version is not None and node.current_version != target_version:
        stmt = (
            select(Version)
            .where(Version.node_id == node_id, Version.version == target_version)
            .options(joinedload(Version.author))
        )
        specific_version = db.session.execute(stmt).scalars().first()
        if not specific_version:
            raise ValueError("Version not found")

        # Patche das Dictionary auf die angefragte Version
        node_dict['title'] = specific_version.title
        node_dict['content'] = specific_version.content
        node_dict['version'] = specific_version.version

        # KI-Zusammenfassung bei alten Versionen ausblenden, um Widersprüche zu vermeiden
        node_dict['ai_summary'] = None
        node_dict['summary_is_current'] = False

        if specific_version.timestamp:
            node_dict['timestamp'] = specific_version.timestamp.isoformat() + 'Z'

        if specific_version.author:
            node_dict['author_id'] = specific_version.author_id
            node_dict['author_name'] = specific_version.author.display_name
    else:
        # Konsistenz: version Feld immer setzen
        node_dict['version'] = node.current_version
        if node.current_version_object:
            if node.current_version_object.timestamp:
                node_dict['timestamp'] = node.current_version_object.timestamp.isoformat() + 'Z'
            if node.current_version_object.author:
                node_dict['author_id'] = node.current_version_object.author_id
                node_dict['author_name'] = node.current_version_object.author.display_name

    # --- Zähler für das Frontend ---
    count_stmt = select(func.count()).select_from(Version).where(with_parent(node, Node.versions))
    version_count = db.session.execute(count_stmt).scalar_one()

    node_dict['has_versions'] = version_count > 1
    node_dict['version_count'] = version_count
    return node_dict


def get_node_versions(node_id: str, vault_id: int, user_id: int) -> list[dict] | None:
    """
    Returns the version metadata history for a node.
    No content is returned, pure stubs for maximum performance without N+1 loops.
    """
    _verify_vault_access(vault_id, user_id)
    node = Node.query.filter_by(id=node_id, vault_id=vault_id).first()
    if not node:
        return None

    # Vermeidet N+1 und unnötige Payloads durch gezielten Select der Spalten.
    stmt = (
        select(
            Version.id,
            Version.node_id,
            Version.version,
            Version.title,
            Version.timestamp,
            Version.author_id,
            User.display_name.label('author_name')
        )
        .outerjoin(User, Version.author_id == User.id)
        .where(Version.node_id == node_id)
        .order_by(Version.version.desc())
        # ToDo: Für sehr alte Nodes könnte man künftig ein limit/offset hier einbauen.
    )
    rows = db.session.execute(stmt).all()

    result = []
    for row in rows:
        result.append({
            'id': row.id,
            'node_id': row.node_id,
            'version': row.version,
            'title': row.title,
            'timestamp': row.timestamp.isoformat() + 'Z',
            'author_id': row.author_id,
            'author_name': row.author_name or 'Unknown',
            'is_stub': True,
        })
    return result


def get_version_by_id(version_id: int, node_id: str, vault_id: int, user_id: int) -> dict | None:
    """Lazy-loads the full content of a single historical version."""
    _verify_vault_access(vault_id, user_id)
    node = Node.query.filter_by(id=node_id, vault_id=vault_id).first()
    if not node:
        return None

    stmt = (
        select(Version)
        .where(Version.id == version_id, with_parent(node, Node.versions))
        .options(joinedload(Version.author))
    )
    version = db.session.execute(stmt).scalars().first()
    if not version:
        return None

    return version.to_dict(include_content=True)


def get_nodes_by_ids(node_ids: list[str], vault_id: int, user_id: int) -> list[dict]:
    """Holt mehrere Nodes nach IDs und prüft den Zugriff."""
    nodes = _get_nodes_by_ids_and_verify_access(node_ids, vault_id, user_id)
    return [node.to_dict(include_content=True) for node in nodes]


def get_nodes_by_ids_for_user(node_ids: List[str], vault_id: int, user_id: int) -> List[Node]:
    """Holt die vollständigen Node-Objekte für eine Liste von IDs."""
    return _get_nodes_by_ids_and_verify_access(node_ids, vault_id, user_id)


def get_content_for_nodes(node_ids: List[str], vault_id: int, user_id: int) -> Dict[str, Any]:
    """Holt und formatiert Inhalte für mehrere Nodes, nachdem der Zugriff verifiziert wurde."""
    if not node_ids:
        raise ValueError("Es muss mindestens eine Node-ID angegeben werden.")
    nodes = _get_nodes_by_ids_and_verify_access(node_ids, vault_id, user_id)
    if not nodes:
        return {"titles": [], "content": ""}

    nodes_by_id = {node.id: node for node in nodes}
    ordered_titles, ordered_contents = [], []
    for node_id in node_ids:
        if node_id in nodes_by_id:
            node = nodes_by_id[node_id]
            ordered_titles.append(node.title)
            content = node.current_version_object.content if node.current_version_object else ""
            ordered_contents.append(
                f"--- START OF DOCUMENT: {node.title} ---\n{content}\n--- END OF DOCUMENT: {node.title} ---"
            )
    full_content = "\n\n".join(ordered_contents)
    return {"titles": ordered_titles, "content": full_content}


# Ein kompilierter Regex zur schnellen Unterscheidung von UUIDs und Titeln.
# Er wird außerhalb der Funktion definiert, damit er nicht bei jedem Aufruf neu kompiliert wird.
UUID_REGEX = re.compile(r'^[0-9a-f]{8}-([0-9a-f]{4}-){3}[0-9a-f]{12}$', re.IGNORECASE)


def resolve_link_targets(targets: list[str], vault_id: int, user_id: int) -> dict:
    """
    Löst eine Liste von Link-Zielen (UUIDs oder Titel) auf und gibt deren Status zurück.
    Dies ist eine hocheffiziente "Batch"-Operation.
    """
    _verify_vault_access(vault_id, user_id)
    if not targets:
        return {}

    # Trenne die Ziele in potenzielle UUIDs und Titel für separate Abfragen.
    # Wir verwenden Sets für eine effiziente Verarbeitung und zur Vermeidung von Duplikaten.
    potential_uuids = {t for t in targets if UUID_REGEX.match(t)}
    potential_titles = {t for t in targets if t not in potential_uuids}

    results = {}

    # 1. Verarbeite starke Links (UUIDs)
    if potential_uuids:
        # Führe eine "sanfte" Abfrage durch: Gib mir alle Nodes, die du mit diesen UUIDs
        # im richtigen Vault finden kannst. Ignoriere die, die nicht existieren.
        found_nodes = (
            Node.query
            .filter(
                Node.id.in_(potential_uuids),
                Node.vault_id == vault_id
            ).all()
        )
        found_ids_map = {node.id: node for node in found_nodes}

        for uuid in potential_uuids:
            if uuid in found_ids_map:
                node = found_ids_map[uuid]
                results[uuid] = {
                    "status": "resolved",
                    "node": {"id": node.id, "title": node.title}
                }
            else:
                results[uuid] = {"status": "unresolved"}

    # 2. Verarbeite schwache Links (Titel)
    if potential_titles:
        # Finde alle Nodes im Vault, deren aktueller Versionstitel (case-insensitive)
        # einem der gesuchten Titel entspricht.
        # SQLAlchemy's `ilike` ist perfekt für case-insensitive exakte Treffer.
        found_nodes_by_title = (
            db.session.query(Node)
            .join(Node.current_version_object)
            .filter(
                Node.vault_id == vault_id,
                # Wir konvertieren sowohl den Spaltenwert als auch die Suchbegriffe
                # in Kleinbuchstaben, um einen case-insensitive Vergleich zu erzwingen.
                func.lower(Version.title).in_([t.lower() for t in potential_titles])
            ).all()
        )
        # Für eine garantierte Case-Insensitive-Suche:
        # .filter(
        #     Node.vault_id == vault_id,
        #     func.lower(Version.title).in_([t.lower() for t in potential_titles])
        # ).all()

        # Gruppiere die gefundenen Nodes nach ihrem Titel (lower-case zur Normalisierung)
        matches_by_title = {}
        for node in found_nodes_by_title:
            title_lower = node.title.lower()
            if title_lower not in matches_by_title:
                matches_by_title[title_lower] = []
            matches_by_title[title_lower].append(node)

        for title in potential_titles:
            # Suche nach den normalisierten Matches
            matches = matches_by_title.get(title.lower(), [])
            if len(matches) == 1:
                node = matches[0]
                results[title] = {
                    "status": "resolved",
                    "node": {"id": node.id, "title": node.title}
                }
            elif len(matches) > 1:
                results[title] = {
                    "status": "ambiguous",
                    "matchCount": len(matches)
                }
            else:
                # Wenn kein Match gefunden wurde, ist der Status "unresolved"
                results[title] = {"status": "unresolved"}
    return results


def search_nodes_for_autocomplete(query: str, vault_id: int, user_id: int) -> list[dict]:
    """
    Sucht nach Nodes für die Autocomplete-Funktion im Editor.
    Gibt eine vereinfachte Liste von Nodes (ID und Titel) zurück.
    """
    _verify_vault_access(vault_id, user_id)
    search_pattern = f"%{query}%"

    # Suche nach Titeln in der `versions`-Tabelle, die zum `current_version` des Nodes gehören
    # und dem Suchmuster entsprechen. Limitiere die Ergebnisse für gute Performance.
    nodes = (
        db.session.query(Node)
        .join(Node.current_version_object)
        .filter(
            Node.vault_id == vault_id,
            Version.title.ilike(search_pattern)  # case-insensitive "contains"
        )
        .order_by(Version.title)  # Sortiere alphabetisch
        .limit(10)  # Sehr wichtig für die UI-Performance!
        .all()
    )

    # Formatiere die Antwort in ein schlankes Format für die UI
    return [
        {"id": node.id, "title": node.title}
        for node in nodes
    ]

# ========================================================================
# WRITE OPERATIONS
# ========================================================================
def create_node(
        title: str,
        content: str,
        parent_id: Optional[str],
        vault_id: int,
        author_id: int,
        icon: Optional[str] = None
) -> Node:
    """Erstellt einen neuen Node und seine initiale Version mit dem Titel."""
    _verify_vault_access(vault_id, author_id)
    if not title or not title.strip():
        raise ValueError("Title cannot be empty.")
    if parent_id:
        parent_node = db.session.get(Node, parent_id)
        if not parent_node:
            raise ValueError(f"Parent node with ID {parent_id} not found.")
        if parent_node.vault_id != vault_id:
            raise PermissionError("Cannot assign a parent from a different vault.")

    # ### KORREKTUR ###
    # Bestimme den Icon-Wert. Wenn keiner übergeben wird, nimm den Standard.
    final_icon = icon if icon is not None else DEFAULT_NODE_ICON

    # Erstelle den Node jetzt MIT dem Icon.
    new_node = Node(
        parent_id=parent_id,
        current_version=1,
        vault_id=vault_id,
        icon=final_icon
    )
    db.session.add(new_node)
    db.session.flush()

    initial_version = Version(
        node_id=new_node.id,
        version=1,
        title=title,
        content=content,
        author_id=author_id
    )
    db.session.add(initial_version)

    db.session.commit()
    rebuild_vault_tree_cache(vault_id)
    return new_node


def update_node(node_id: str, vault_id: int, user_id: int, title: Optional[str] = None,
                content: Optional[str] = None) -> Node:
    """Aktualisiert Titel und/oder Inhalt eines Nodes und erstellt IMMER eine neue Version."""
    _verify_vault_access(vault_id, user_id)
    node = Node.query.filter_by(id=node_id, vault_id=vault_id).options(joinedload(Node.current_version_object)).first()
    if not node:
        raise ValueError("Node not found in the specified vault")
    last_version = node.current_version_object
    if not last_version:
        raise ValueError("Cannot update a node with no existing versions.")
    current_title = last_version.title
    current_content = last_version.content

    # Wenn weder Titel noch Inhalt übergeben wurden, gibt es nichts zu tun.
    if title is None and content is None:
        return node
    new_title = title if title is not None else current_title
    new_content = content if content is not None else current_content

    # Wir erstellen keine neue Version, wenn sich absolut nichts geändert hat.
    if new_title == current_title and new_content == current_content:
        return node

    # Der Titel darf nicht leer sein.
    if not new_title or not new_title.strip():
        raise ValueError("Title cannot be empty.")

    next_version_number = node.current_version + 1
    new_version = Version(
        node_id=node.id,
        version=next_version_number,
        title=new_title,
        content=new_content,
        author_id=user_id
    )
    db.session.add(new_version)
    node.current_version = next_version_number
    db.session.commit()

    # Reload with current_version_object eagerly so the caller can call .to_dict()
    updated_node = Node.query.options(joinedload(Node.current_version_object)).filter_by(
        id=node_id).one()
    rebuild_vault_tree_cache(vault_id)
    return updated_node


def update_node_ai_summary(node_id: str, vault_id: int, user_id: int, ai_summary: str) -> Node:
    """Updates the ai_summary field and marks it as current. No new version created."""
    _verify_vault_access(vault_id, user_id)
    node = Node.query.filter_by(id=node_id, vault_id=vault_id).first()
    if not node:
        raise ValueError("Node not found in the specified vault.")
    node.ai_summary = ai_summary
    node.summary_is_current = True
    db.session.commit()
    db.session.refresh(node)
    rebuild_vault_tree_cache(vault_id)
    return node


def move_node(node_id: str, new_parent_id: str | None, vault_id: int, user_id: int) -> Node:
    """Bewegt einen Node zu einem neuen Parent (keine neue Version)."""
    _verify_vault_access(vault_id, user_id)
    if str(node_id) == str(new_parent_id):
        raise ValueError("Cannot move a node into itself.")
    node_to_move = Node.query.filter_by(id=node_id, vault_id=vault_id).first()
    if not node_to_move:
        raise ValueError("Node to move not found in the specified vault.")
    if new_parent_id:
        new_parent = Node.query.filter_by(id=new_parent_id, vault_id=vault_id).first()
        if not new_parent:
            raise ValueError("Target parent node not found in the specified vault.")
        if _is_descendant(node_id, new_parent_id, vault_id):
            raise ValueError("Cannot move a node into one of its own children.")

    node_to_move.parent_id = new_parent_id
    db.session.commit()
    rebuild_vault_tree_cache(vault_id)
    return node_to_move


def update_node_icon(node_id: str, vault_id: int, user_id: int, icon: Optional[str]) -> Node:
    """Aktualisiert das Icon eines Nodes. Das Icon muss ein gültiger, vordefinierter String oder None sein."""
    _verify_vault_access(vault_id, user_id)
    node = Node.query.filter_by(id=node_id, vault_id=vault_id).first()
    if not node:
        raise ValueError("Node not found in the specified vault.")
    processed_icon = icon
    if isinstance(icon, str) and icon.lower() in ["none", "null"]:
        processed_icon = None
    if processed_icon is not None and processed_icon not in ALLOWED_ICONS:
        raise ValueError(f"Invalid icon value: '{icon}'. Please use a valid icon string.")

    node.icon = processed_icon
    db.session.commit()
    db.session.refresh(node)
    rebuild_vault_tree_cache(vault_id)
    return node


def delete_node(node_id: str, vault_id: int, user_id: int):
    """
    Löscht einen Node. Kind-Nodes werden dabei an den Parent des gelöschten
    Nodes weitergereicht ("adoptiert"). Wenn der gelöschte Node ein Top-Level-Node
    war, werden seine Kinder ebenfalls zu Top-Level-Nodes.
    """
    _verify_vault_access(vault_id, user_id)
    node_to_delete = Node.query.filter_by(id=node_id, vault_id=vault_id).first()
    if not node_to_delete:
        raise ValueError("Node not found in the specified vault")

    # Bestimme den neuen Parent für die Kinder: Es ist der Parent des zu löschenden Nodes.
    # Wenn der gelöschte Node selbst ein Top-Level-Node war, wird dieser Wert `None` sein.
    new_parent_for_children = node_to_delete.parent_id

    # Aktualisiere die Kinder, sodass sie auf den neuen Parent zeigen.
    # Ihre parent_id wird zur parent_id des gelöschten Nodes.
    Node.query.filter_by(parent_id=node_id, vault_id=vault_id).update(
        {"parent_id": new_parent_for_children}, synchronize_session='fetch'
    )

    # Den Node selbst löschen. Versionen werden durch 'cascade' automatisch mitgelöscht.
    db.session.delete(node_to_delete)
    db.session.commit()
    rebuild_vault_tree_cache(vault_id)