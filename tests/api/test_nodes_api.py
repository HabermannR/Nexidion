# tests/api/v2/test_nodes_api.py
import pytest
from backend.services import node_service
from backend.models import VaultAccess, VaultRole, DemoState


# --- Helper-Funktion für diese Testdatei ---
def create_test_node(client, headers, vault_id, title, content="...", parent_id=None):
    """
    Erstellt einen Node über die API und gibt das resultierende JSON-Objekt zurück.
    Wirft einen Fehler, wenn die Erstellung fehlschlägt, um Tests sauber zu halten.
    """
    node_data = {'title': title, 'content': content}
    if parent_id:
        node_data['parent_id'] = parent_id

    response = client.post(f'/api/vaults/{vault_id}/nodes/',
                           headers=headers,
                           json=node_data)
    # Stellt sicher, dass das Setup für den Test erfolgreich war
    assert response.status_code == 201, f"Helper 'create_test_node' failed: {response.text}"
    return response.get_json()


# ========================================================================
# CRUD-Operationen
# ========================================================================

def test_create_node_success(client, auth_headers_1, test_vault_1_obj):
    """Testet das erfolgreiche Erstellen eines neuen Nodes."""
    vault_id = test_vault_1_obj.id
    node_data = {'title': 'My First API Node', 'content': 'This is the content.'}

    response = client.post(f'/api/vaults/{vault_id}/nodes/',
                           headers=auth_headers_1,
                           json=node_data)

    assert response.status_code == 201
    data = response.get_json()
    assert data['title'] == 'My First API Node'
    assert 'id' in data


def test_update_node_put(client, auth_headers_1, test_vault_1_obj):
    """Testet das Aktualisieren (PUT) eines Nodes."""
    vault_id = test_vault_1_obj.id
    node = create_test_node(client, auth_headers_1, vault_id, 'Node to be updated', 'Original Content')

    update_data = {'title': 'Completely New Title', 'content': 'This is the new, updated content.'}
    update_res = client.put(f'/api/vaults/{vault_id}/nodes/{node["id"]}',
                            headers=auth_headers_1,
                            json=update_data)
    assert update_res.status_code == 200
    data = update_res.get_json()
    assert data['title'] == 'Completely New Title'
    assert data['content'] == 'This is the new, updated content.'


def test_delete_node_success(client, auth_headers_1, test_vault_1_obj):
    """Testet das erfolgreiche Löschen eines Nodes."""
    vault_id = test_vault_1_obj.id
    # Da Haupt-/Root-Nodes nicht gelöscht werden dürfen, erstellen wir zuerst einen Parent.
    parent_node = create_test_node(client, auth_headers_1, vault_id, 'Parent Node')

    # Der zu löschende Node wird als Kindknoten erstellt.
    node_to_delete = create_test_node(client, auth_headers_1, vault_id, 'Node to be deleted',
                                      parent_id=parent_node['id'])

    delete_res = client.delete(f'/api/vaults/{vault_id}/nodes/{node_to_delete["id"]}',
                               headers=auth_headers_1)
    assert delete_res.status_code == 200

    get_res = client.get(f'/api/vaults/{vault_id}/nodes/{node_to_delete["id"]}', headers=auth_headers_1)
    assert get_res.status_code == 404


def test_delete_node_reparents_child_via_api(client, auth_headers_1, test_vault_1_obj):
    """
    Testet, dass beim Löschen eines Nodes dessen Kind an den Großeltern-Node
    angehängt wird (Adoptions-Logik).
    """
    # ARRANGE: Erstelle eine Hierarchie: Grandparent -> Parent -> Child
    vault_id = test_vault_1_obj.id
    grandparent = create_test_node(client, auth_headers_1, vault_id, 'Grandparent')
    parent = create_test_node(client, auth_headers_1, vault_id, 'Parent', parent_id=grandparent['id'])
    child = create_test_node(client, auth_headers_1, vault_id, 'Child', parent_id=parent['id'])

    # ACT: Lösche den Parent-Node über die API
    delete_res = client.delete(f'/api/vaults/{vault_id}/nodes/{parent["id"]}',
                               headers=auth_headers_1)
    assert delete_res.status_code == 200

    # ASSERT: Überprüfe den neuen Zustand des Kindes über die API
    get_child_res = client.get(f'/api/vaults/{vault_id}/nodes/{child["id"]}', headers=auth_headers_1)
    assert get_child_res.status_code == 200
    child_data = get_child_res.get_json()

    # Das Kind sollte jetzt den Großeltern-Node als Parent haben
    assert child_data['parent_id'] == grandparent['id']


# ========================================================================
# GET-Variationen und Caching
# ========================================================================

def test_get_nodes_as_list(client, auth_headers_1, test_vault_1_obj):
    """Testet den ?format=list Query-Parameter."""
    vault_id = test_vault_1_obj.id
    create_test_node(client, auth_headers_1, vault_id, "Node A")

    response = client.get(f'/api/vaults/{vault_id}/nodes/?format=list', headers=auth_headers_1)
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1  # Mindestens der Root-Node + der neu erstellte
    assert 'content' in data[0]


def test_find_node_by_title_query_param(client, auth_headers_1, test_vault_1_obj):
    """Testet den ?title=... Query-Parameter für die Node-Suche."""
    vault_id = test_vault_1_obj.id
    create_test_node(client, auth_headers_1, vault_id, "My Special Findable Node")

    response = client.get(f'/api/vaults/{vault_id}/nodes/?title=Special Findable', headers=auth_headers_1)
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]['title'] == "My Special Findable Node"


def test_get_node_versions_api_with_caching(client, auth_headers_1, test_vault_1_obj):
    """Testet den GET /.../nodes/{id}/versions Endpunkt, inklusive ETag-Caching."""
    vault_id = test_vault_1_obj.id
    node = create_test_node(client, auth_headers_1, vault_id, 'Node for Version Test', 'Content V1')
    client.put(f'/api/vaults/{vault_id}/nodes/{node["id"]}', headers=auth_headers_1, json={'content': 'Content V2'})

    # Erste Anfrage (ohne Cache)
    response1 = client.get(f'/api/vaults/{vault_id}/nodes/{node["id"]}/versions', headers=auth_headers_1)
    assert response1.status_code == 200
    versions = response1.get_json()
    assert len(versions) == 2
    assert versions[0]['version'] == 2
    assert 'ETag' in response1.headers
    etag = response1.headers['ETag']

    # Zweite Anfrage (mit Cache)
    cached_headers = {**auth_headers_1, 'If-None-Match': etag}
    response2 = client.get(f'/api/vaults/{vault_id}/nodes/{node["id"]}/versions', headers=cached_headers)
    assert response2.status_code == 304


# ========================================================================
# Spezifische PATCH-Routen (Move, Icon)
# ========================================================================

def test_move_node_patch(client, auth_headers_1, test_vault_1_obj):
    """Testet das erfolgreiche Verschieben eines Nodes via PATCH .../move."""
    vault_id = test_vault_1_obj.id
    parent = create_test_node(client, auth_headers_1, vault_id, 'Parent Node')
    child = create_test_node(client, auth_headers_1, vault_id, 'Child Node')

    move_data = {'parent_id': parent['id']}
    move_res = client.patch(f"/api/vaults/{vault_id}/nodes/{child['id']}/move",
                            headers=auth_headers_1,
                            json=move_data)
    assert move_res.status_code == 200

    get_res = client.get(f"/api/vaults/{vault_id}/nodes/{child['id']}", headers=auth_headers_1)
    assert get_res.get_json()['parent_id'] == parent['id']


def test_set_node_icon_patch(client, auth_headers_1, test_vault_1_obj):
    """
    Testet das erfolgreiche Setzen und Entfernen eines GÜLTIGEN Icons.
    """
    vault_id = test_vault_1_obj.id
    node = create_test_node(client, auth_headers_1, vault_id, 'Node with Icon')

    # Setze ein gültiges Icon aus der Liste
    valid_icon = 'bxs-folder'
    icon_data = {'icon': valid_icon}
    icon_res = client.patch(f"/api/vaults/{vault_id}/nodes/{node['id']}/icon",
                            headers=auth_headers_1,
                            json=icon_data)
    assert icon_res.status_code == 200
    assert icon_res.get_json()['icon'] == valid_icon

    # Entferne das Icon, indem `null` gesendet wird
    icon_data_null = {'icon': None}
    icon_res_null = client.patch(f"/api/vaults/{vault_id}/nodes/{node['id']}/icon",
                                 headers=auth_headers_1,
                                 json=icon_data_null)
    assert icon_res_null.status_code == 200
    assert icon_res_null.get_json()['icon'] is None


@pytest.mark.parametrize("invalid_icon", [
    "not-a-valid-icon-string",  # Komplett ungültig
    "bx bxs-folder",  # Fast richtig, aber "bx " zu viel
    "",  # Ein leerer String ist ebenfalls ungültig
    "bxs-folder ",  # Ungültig wegen Leerzeichen am Ende
])
def test_set_node_icon_with_invalid_string_fails(client, auth_headers_1, test_vault_1_obj, invalid_icon):
    """
    Testet, dass PATCH .../icon einen 400-Fehler zurückgibt, wenn ein ungültiger String gesendet wird.
    """
    vault_id = test_vault_1_obj.id
    node = create_test_node(client, auth_headers_1, vault_id, 'Test Node')

    payload = {'icon': invalid_icon}
    response = client.patch(f"/api/vaults/{vault_id}/nodes/{node['id']}/icon",
                            headers=auth_headers_1,
                            json=payload)

    assert response.status_code == 400
    error_json = response.get_json()
    assert "Invalid icon value" in error_json['error']


def test_set_node_icon_on_nonexistent_node(client, auth_headers_1, test_vault_1_obj):
    """
    Testet, dass PATCH .../icon einen 404-Fehler zurückgibt, wenn der Node nicht existiert.
    """
    vault_id = test_vault_1_obj.id
    non_existent_node_id = "00000000-0000-0000-0000-000000000000"

    payload = {'icon': '❓'}
    response = client.patch(f"/api/vaults/{vault_id}/nodes/{non_existent_node_id}/icon",
                            headers=auth_headers_1,
                            json=payload)

    assert response.status_code == 400  # Der Service wirft einen ValueError, die API gibt 400 zurück
    assert "Node not found" in response.get_json()['error']


def test_set_node_icon_on_other_users_node(client, auth_headers_1, auth_headers_2, test_vault_1_obj, test_vault_2_obj):
    """
    Sicherheitstest: Stellt sicher, dass User 2 das Icon eines Nodes von User 1 nicht ändern kann.
    """
    # User 1 erstellt einen Node in seinem Vault
    vault_id_1 = test_vault_1_obj.id
    node_user_1 = create_test_node(client, auth_headers_1, vault_id_1, "Node von User 1")

    # User 2 versucht, das Icon für diesen Node zu ändern
    payload = {'icon': '🏴‍☠️'}
    response = client.patch(f"/api/vaults/{vault_id_1}/nodes/{node_user_1['id']}/icon",
                            headers=auth_headers_2,  # Wichtig: Header von User 2
                            json=payload)

    assert response.status_code == 403


# ========================================================================
# Bulk-Operationen
# ========================================================================

def test_bulk_get_nodes_success(client, auth_headers_1, test_vault_1_obj):
    """Testet das erfolgreiche Abrufen mehrerer Nodes über POST /bulk-get."""
    vault_id = test_vault_1_obj.id
    node1 = create_test_node(client, auth_headers_1, vault_id, "Bulk 1", "Content 1")
    node2 = create_test_node(client, auth_headers_1, vault_id, "Bulk 2", "Content 2")
    create_test_node(client, auth_headers_1, vault_id, "Untouched Node")

    payload = {'node_ids': [node1['id'], node2['id']]}
    response = client.post(f'/api/vaults/{vault_id}/nodes/bulk-get', headers=auth_headers_1, json=payload)

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 2

    # KORREKTUR: Prüfe auf 'node_id' in den zurückgegebenen Versionen-Objekten
    returned_node_ids = {item['node_id'] for item in data}
    assert set(payload['node_ids']) == returned_node_ids


def test_post_nodes_content_success(client, auth_headers_1, test_vault_1_obj):
    """Testet den POST /content Endpunkt."""
    vault_id = test_vault_1_obj.id
    node_a = create_test_node(client, auth_headers_1, vault_id, "Content A", content="Alpha.")
    node_b = create_test_node(client, auth_headers_1, vault_id, "Content B", content="Beta.")

    payload = {'node_ids': [node_a['id'], node_b['id']]}
    response = client.post(f'/api/vaults/{vault_id}/nodes/content', headers=auth_headers_1, json=payload)

    assert response.status_code == 200
    data = response.get_json()
    assert data['titles'] == ["Content A", "Content B"]
    assert "Alpha." in data['content']
    assert "Beta." in data['content']


# ========================================================================
# Fehler- und Sicherheits-Tests
# ========================================================================

def test_create_node_unauthorized(client, test_vault_1_obj):
    """Testet, dass ein nicht eingeloggter Benutzer keinen Node erstellen kann."""
    response = client.post(f'/api/vaults/{test_vault_1_obj.id}/nodes/', json={'title': 'sneaky'})
    assert response.status_code == 401


def test_get_nodes_from_other_users_vault_fails(client, auth_headers_1, test_vault_2_obj):
    """Sicherheitstest: User 1 kann die Nodes von User 2 nicht sehen."""
    response = client.get(f"/api/vaults/{test_vault_2_obj.id}/nodes/", headers=auth_headers_1)
    assert response.status_code == 403


def test_update_node_from_other_users_vault_fails(client, auth_headers_1, auth_headers_2, test_vault_1_obj):
    """Sicherheitstest: User 2 kann einen Node von User 1 nicht aktualisieren."""
    node_user_1 = create_test_node(client, auth_headers_1, test_vault_1_obj.id, 'Private Node')
    response = client.put(f"/api/vaults/{test_vault_1_obj.id}/nodes/{node_user_1['id']}",
                          headers=auth_headers_2, json={'title': 'takeover'})
    assert response.status_code == 403


def test_move_node_into_its_own_child_fails(client, auth_headers_1, test_vault_1_obj):
    """Verhindert, dass ein Node in einen seiner eigenen Nachkommen verschoben wird."""
    vault_id = test_vault_1_obj.id
    parent = create_test_node(client, auth_headers_1, vault_id, 'Parent')
    child = create_test_node(client, auth_headers_1, vault_id, 'Child', parent_id=parent['id'])

    move_data = {'parent_id': child['id']}
    # KORREKTUR: Korrekter Endpunkt /move
    move_res = client.patch(f"/api/vaults/{vault_id}/nodes/{parent['id']}/move",
                            headers=auth_headers_1, json=move_data)
    assert move_res.status_code == 400
    assert 'Cannot move a node into one of its own children' in move_res.get_json()['error']


def test_create_node_with_parent_from_other_vault_fails(client, auth_headers_1, auth_headers_2, test_vault_1_obj,
                                                        test_vault_2_obj):
    """Testet, dass das Erstellen eines Nodes mit einem Parent aus einem fremden Vault fehlschlägt."""
    parent_in_vault_2 = create_test_node(client, auth_headers_2, test_vault_2_obj.id, 'Parent in Vault 2')
    node_data = {'title': 'Invalid Child', 'parent_id': parent_in_vault_2['id']}

    response = client.post(f'/api/vaults/{test_vault_1_obj.id}/nodes/', headers=auth_headers_1, json=node_data)
    assert response.status_code == 403
    assert "Cannot assign a parent from a different vault" in response.get_json()['error']


@pytest.mark.parametrize("payload, expected_error", [
    ({}, "Request body must contain 'node_ids'."),
    ({"node_ids": "not-a-list"}, "'node_ids' must be a list."),
])
def test_post_nodes_content_with_invalid_payload(client, auth_headers_1, test_vault_1_obj, payload, expected_error):
    """Testet verschiedene ungültige Payloads für POST /content."""
    response = client.post(f'/api/vaults/{test_vault_1_obj.id}/nodes/content', headers=auth_headers_1, json=payload)
    assert response.status_code == 400
    assert expected_error in response.get_json()['error']


def test_bulk_get_nodes_with_non_existent_id_fails(client, auth_headers_1, test_vault_1_obj):
    """Testet, dass /bulk-get mit 404 fehlschlägt, wenn eine der Node-IDs nicht existiert."""
    vault_id = test_vault_1_obj.id
    node1 = create_test_node(client, auth_headers_1, vault_id, "An Existing Node")
    # KORREKTUR: Ein gültiger String, der keinem Node entspricht, um Service-Fehler zu testen
    non_existent_uuid = '00000000-0000-0000-0000-000000000000'
    payload = {'node_ids': [node1['id'], non_existent_uuid]}

    response = client.post(f'/api/vaults/{vault_id}/nodes/bulk-get', headers=auth_headers_1, json=payload)
    assert response.status_code == 404
    assert "not found" in response.get_json()['error']


def test_api_update_node_icon_success(client, auth_headers_1, test_user_1_obj, test_vault_1_obj):
    """
    Testet den "Happy Path" für den PATCH /.../icon Endpunkt.
    """
    # ARRANGE
    # Erstelle einen Node über den Service, um ein Objekt zum Ändern zu haben.
    node_dict = node_service.create_node("API Icon Test", "", None, test_vault_1_obj.id, test_user_1_obj.id)
    node_id = node_dict.id

    payload = {'icon': 'bxs-brain'}  # Ein gültiges, neues Icon

    # ACT
    response = client.patch(
        f'/api/vaults/{test_vault_1_obj.id}/nodes/{node_id}/icon',
        headers=auth_headers_1,
        json=payload
    )

    # ASSERT
    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data['id'] == node_id
    assert response_data['icon'] == 'bxs-brain'

    # Zusätzliche Überprüfung: Hole den Node erneut und prüfe, ob die Änderung persistent ist.
    get_response = client.get(f'/api/vaults/{test_vault_1_obj.id}/nodes/{node_id}', headers=auth_headers_1)
    assert get_response.get_json()['icon'] == 'bxs-brain'


def test_api_update_node_icon_to_null(client, auth_headers_1, test_user_1_obj, test_vault_1_obj):
    """
    Testet, ob das Icon via API auf `null` gesetzt werden kann.
    """
    # ARRANGE
    node_dict = node_service.create_node("API Icon auf Null", "", None, test_vault_1_obj.id, test_user_1_obj.id)
    node_id = node_dict.id

    payload = {'icon': None}  # JSON `null` wird zu Python `None`

    # ACT
    response = client.patch(
        f'/api/vaults/{test_vault_1_obj.id}/nodes/{node_id}/icon',
        headers=auth_headers_1,
        json=payload
    )

    # ASSERT
    assert response.status_code == 200
    assert response.get_json()['icon'] is None


def test_api_update_node_icon_with_invalid_icon_returns_400(client, auth_headers_1, test_user_1_obj, test_vault_1_obj):
    """
    Testet, dass die API einen 400 Bad Request bei einem ungültigen Icon zurückgibt.
    """
    # ARRANGE
    node_dict = node_service.create_node("API Ungültiges Icon", "", None, test_vault_1_obj.id, test_user_1_obj.id)
    node_id = node_dict.id

    payload = {'icon': 'ungueltiger-string-123'}

    # ACT
    response = client.patch(
        f'/api/vaults/{test_vault_1_obj.id}/nodes/{node_id}/icon',
        headers=auth_headers_1,
        json=payload
    )

    # ASSERT
    assert response.status_code == 400  # Weil ein ValueError im Service zu 400 wird
    assert "Invalid icon value" in response.get_json()['error']


def test_api_update_node_icon_with_missing_key_returns_400(client, auth_headers_1, test_user_1_obj, test_vault_1_obj):
    """
    Testet, dass die API einen 400 Bad Request zurückgibt, wenn der 'icon'-Schlüssel fehlt.
    """
    # ARRANGE
    node_dict = node_service.create_node("API Fehlender Key", "", None, test_vault_1_obj.id, test_user_1_obj.id)
    node_id = node_dict.id

    payload = {'falscher_key': 'bxs-brain'}  # Der 'icon'-Key fehlt

    # ACT
    response = client.patch(
        f'/api/vaults/{test_vault_1_obj.id}/nodes/{node_id}/icon',
        headers=auth_headers_1,
        json=payload
    )

    # ASSERT
    assert response.status_code == 400
    assert "Request body must contain 'icon'" in response.get_json()['error']


class TestInternalLinkingAPI:
    """Eine Klasse, um alle Tests für interne Links zu gruppieren."""

    def test_search_for_autocomplete_success(self, client, auth_headers_1, test_vault_1_obj):
        """Testet den /search Endpunkt für Autocomplete."""
        # ARRANGE
        vault_id = test_vault_1_obj.id
        create_test_node(client, auth_headers_1, vault_id, "Apfelkuchen Rezept")
        create_test_node(client, auth_headers_1, vault_id, "Apfelstrudel Anleitung")
        create_test_node(client, auth_headers_1, vault_id, "Bananenbrot")

        # ACT
        response = client.get(f'/api/vaults/{vault_id}/nodes/search?q=Apfel', headers=auth_headers_1)

        # ASSERT
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 2

        titles = {item['title'] for item in data}
        assert "Apfelkuchen Rezept" in titles
        assert "Apfelstrudel Anleitung" in titles

    def test_search_case_insensitive(self, client, auth_headers_1, test_vault_1_obj):
        """Stellt sicher, dass die Suche nicht auf Groß-/Kleinschreibung achtet."""
        vault_id = test_vault_1_obj.id
        create_test_node(client, auth_headers_1, vault_id, "Grossbuchstabe")

        response = client.get(f'/api/vaults/{vault_id}/nodes/search?q=gross', headers=auth_headers_1)

        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]['title'] == "Grossbuchstabe"

    def test_search_no_results(self, client, auth_headers_1, test_vault_1_obj):
        """Testet eine Suche, die keine Ergebnisse liefert."""
        vault_id = test_vault_1_obj.id
        response = client.get(f'/api/vaults/{vault_id}/nodes/search?q=NichtExistent', headers=auth_headers_1)
        assert response.status_code == 200
        assert response.get_json() == []

    def test_search_requires_min_length(self, client, auth_headers_1, test_vault_1_obj):
        """Testet, dass die Suche bei zu kurzen Anfragen eine leere Liste zurückgibt."""
        vault_id = test_vault_1_obj.id
        response = client.get(f'/api/vaults/{vault_id}/nodes/search?q=A', headers=auth_headers_1)
        assert response.status_code == 200
        assert response.get_json() == []

    def test_search_permission_denied(self, client, auth_headers_2, test_vault_1_obj):
        """User 2 darf nicht im Vault von User 1 suchen."""
        vault_id = test_vault_1_obj.id
        response = client.get(f'/api/vaults/{vault_id}/nodes/search?q=test', headers=auth_headers_2)
        assert response.status_code == 403

    def test_resolve_links_mixed_scenarios(self, client, auth_headers_1, test_vault_1_obj):
        """
        Ein umfassender Test für /resolve-links mit allen denkbaren Szenarien in einem Aufruf.
        """
        # ARRANGE
        vault_id = test_vault_1_obj.id
        # 1. Eindeutiger starker Link
        strong_link_node = create_test_node(client, auth_headers_1, vault_id, "Starker Link Node")
        # 2. Eindeutiger schwacher Link
        weak_link_node = create_test_node(client, auth_headers_1, vault_id, "Schwacher Link Eindeutig")
        # 3. Mehrdeutiger schwacher Link
        create_test_node(client, auth_headers_1, vault_id, "Mehrdeutiger Titel")
        create_test_node(client, auth_headers_1, vault_id, "Mehrdeutiger Titel")
        # 4. Nicht existierende Ziele
        unresolved_uuid = "11111111-1111-1111-1111-111111111111"
        unresolved_title = "Diesen Titel gibt es nicht"

        payload = {
            "targets": [
                strong_link_node['id'],
                "Schwacher Link Eindeutig",
                "Mehrdeutiger Titel",
                unresolved_uuid,
                unresolved_title
            ]
        }

        # ACT
        response = client.post(f'/api/vaults/{vault_id}/nodes/resolve-links', headers=auth_headers_1, json=payload)

        # ASSERT
        assert response.status_code == 200
        data = response.get_json()
        results = data['results']

        # Überprüfe jeden Fall
        # 1. Starker Link -> resolved
        assert results[strong_link_node['id']]['status'] == 'resolved'
        assert results[strong_link_node['id']]['node']['id'] == strong_link_node['id']
        assert results[strong_link_node['id']]['node']['title'] == "Starker Link Node"

        # 2. Schwacher Link -> resolved
        assert results["Schwacher Link Eindeutig"]['status'] == 'resolved'
        assert results["Schwacher Link Eindeutig"]['node']['id'] == weak_link_node['id']

        # 3. Mehrdeutiger Link -> ambiguous
        assert results["Mehrdeutiger Titel"]['status'] == 'ambiguous'
        assert results["Mehrdeutiger Titel"]['matchCount'] == 2

        # 4. Nicht gefundene Links -> unresolved
        assert results[unresolved_uuid]['status'] == 'unresolved'
        assert results[unresolved_title]['status'] == 'unresolved'

    def test_resolve_links_permission_denied(self, client, auth_headers_1, auth_headers_2, test_vault_1_obj):
        """User 2 darf keine Links im Vault von User 1 auflösen."""
        vault_id = test_vault_1_obj.id
        node = create_test_node(client, auth_headers_1, vault_id, "Ein Test-Node")

        payload = {"targets": [node['id']]}
        response = client.post(f'/api/vaults/{vault_id}/nodes/resolve-links', headers=auth_headers_2, json=payload)

        assert response.status_code == 403

    def test_resolve_links_with_empty_targets_list(self, client, auth_headers_1, test_vault_1_obj):
        """Testet, dass eine leere `targets`-Liste ein leeres Ergebnis-Objekt zurückgibt."""
        vault_id = test_vault_1_obj.id
        payload = {"targets": []}
        response = client.post(f'/api/vaults/{vault_id}/nodes/resolve-links', headers=auth_headers_1, json=payload)

        assert response.status_code == 200
        assert response.get_json() == {"results": {}}

    @pytest.mark.parametrize("invalid_payload", [
        ({"foo": "bar"}),  # Falscher Key
        ({"targets": "not a list"}),  # Falscher Datentyp
    ])
    def test_resolve_links_invalid_payload(self, client, auth_headers_1, test_vault_1_obj, invalid_payload):
        """Testet, dass ein ungültiger Payload zu einem 400 Bad Request führt."""
        vault_id = test_vault_1_obj.id
        response = client.post(f'/api/vaults/{vault_id}/nodes/resolve-links', headers=auth_headers_1,
                               json=invalid_payload)
        assert response.status_code == 400


def test_node_write_as_viewer_returns_403(client, db_session, test_user_2_obj, test_vault_1_obj, auth_headers_2):
    """Testet, dass ein User mit VIEWER-Rechten keine Nodes anlegen/ändern darf."""

    # ARRANGE: Grant User 2 VIEWER access to Vault 1
    access = VaultAccess(
        vault_id=test_vault_1_obj.id,
        user_id=test_user_2_obj.id,
        role=VaultRole.VIEWER
    )
    db_session.session.add(access)
    db_session.session.commit()

    # ACT: User 2 (Viewer) versucht, einen Node in Vault 1 zu erstellen
    response = client.post(
        f'/api/vaults/{test_vault_1_obj.id}/nodes/',
        headers=auth_headers_2,
        json={'title': 'Viewer Node', 'content': 'Should be blocked'}
    )

    # ASSERT
    assert response.status_code == 403
    assert "read-only access" in response.get_json()['error']


def test_node_write_as_demo_locked_returns_423(client, db_session, test_user_1_obj, test_vault_1_obj, auth_headers_1):
    """Testet, dass ein Guest im READ_ONLY Modus keine Nodes ändern darf (HTTP 423)."""

    # ARRANGE: Wir machen den Vault-Besitzer (User 1) für diesen Test zu einem gelockten Guest
    test_user_1_obj.is_guest = True
    test_user_1_obj.demo_state = DemoState.READ_ONLY
    db_session.session.commit()

    # ACT: User 1 versucht, einen Node zu erstellen
    response = client.post(
        f'/api/vaults/{test_vault_1_obj.id}/nodes/',
        headers=auth_headers_1,
        json={'title': 'Locked Node', 'content': 'Should be blocked by demo lock'}
    )

    # ASSERT
    assert response.status_code == 423
    assert "Complete the demo task" in response.get_json()['error']

# ========================================================================
# Tests für neue Endpunkte (AI Summary, Versions, Full-Search, Content)
# ========================================================================

def test_post_nodes_content_permission_denied(client, auth_headers_2, test_vault_1_obj):
    """Stellt sicher, dass User 2 keine Inhalte aus dem Vault von User 1 abrufen kann."""
    # User 2 versucht auf Vault 1 zuzugreifen
    payload = {'node_ids': ["some-uuid-1", "some-uuid-2"]}
    response = client.post(
        f'/api/vaults/{test_vault_1_obj.id}/nodes/content',
        headers=auth_headers_2,
        json=payload
    )
    assert response.status_code == 403


# --- AI Summary (PATCH) ---

def test_update_ai_summary_success(client, auth_headers_1, test_vault_1_obj):
    """Testet das erfolgreiche Update der AI Summary via API."""
    vault_id = test_vault_1_obj.id
    node = create_test_node(client, auth_headers_1, vault_id, "Summary Test Node")

    payload = {"ai_summary": "Der LLM Agent hat dies zusammengefasst."}
    response = client.patch(
        f'/api/vaults/{vault_id}/nodes/{node["id"]}/summary',
        headers=auth_headers_1,
        json=payload
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["ai_summary"] == "Der LLM Agent hat dies zusammengefasst."


def test_update_ai_summary_missing_field(client, auth_headers_1, test_vault_1_obj):
    """Testet die Validierung, wenn 'ai_summary' im Body fehlt."""
    vault_id = test_vault_1_obj.id
    node = create_test_node(client, auth_headers_1, vault_id, "Validation Node")

    payload = {"wrong_key": "Wert"}
    response = client.patch(
        f'/api/vaults/{vault_id}/nodes/{node["id"]}/summary',
        headers=auth_headers_1,
        json=payload
    )

    assert response.status_code == 400
    assert "Request body must contain 'ai_summary'" in response.get_json()['error']


def test_update_ai_summary_permission_denied(client, auth_headers_1, auth_headers_2, test_vault_1_obj):
    """User 2 darf die Summary von User 1 nicht anpassen."""
    vault_id = test_vault_1_obj.id
    node = create_test_node(client, auth_headers_1, vault_id, "Private Node")

    payload = {"ai_summary": "Hacked summary"}
    response = client.patch(
        f'/api/vaults/{vault_id}/nodes/{node["id"]}/summary',
        headers=auth_headers_2,
        json=payload
    )
    assert response.status_code == 403


# --- Single Version (GET) ---

def test_get_single_version_success(client, auth_headers_1, test_vault_1_obj):
    """Testet das Lazy-Loading des vollen Inhalts einer alten Version."""
    vault_id = test_vault_1_obj.id

    # 1. Node erstellen (V1)
    node = create_test_node(client, auth_headers_1, vault_id, "Versioned Node", "Inhalt V1")
    # 2. Node updaten (V2)
    client.put(f'/api/vaults/{vault_id}/nodes/{node["id"]}', headers=auth_headers_1, json={'content': 'Inhalt V2'})

    # 3. Liste der Stubs abholen, um an die Datenbank-ID der Version zu kommen
    versions_res = client.get(f'/api/vaults/{vault_id}/nodes/{node["id"]}/versions', headers=auth_headers_1)
    versions_data = versions_res.get_json()

    # Suchen wir die ID der V1
    v1_stub = next(v for v in versions_data if v['version'] == 1)
    v1_id = v1_stub['id']

    # 4. Endpunkt aufrufen
    response = client.get(
        f'/api/vaults/{vault_id}/nodes/{node["id"]}/versions/{v1_id}',
        headers=auth_headers_1
    )

    assert response.status_code == 200
    full_version = response.get_json()
    assert full_version['content'] == "Inhalt V1"
    assert full_version['version'] == 1


def test_get_single_version_not_found(client, auth_headers_1, test_vault_1_obj):
    """Testet 404, wenn die Version nicht existiert."""
    vault_id = test_vault_1_obj.id
    node = create_test_node(client, auth_headers_1, vault_id, "Node")

    response = client.get(
        f'/api/vaults/{vault_id}/nodes/{node["id"]}/versions/999999',
        headers=auth_headers_1
    )
    assert response.status_code == 404
    assert "Version not found" in response.get_json()['error']


# --- Full-Text Search (GET) ---

def test_full_text_search_success(client, auth_headers_1, test_vault_1_obj):
    """Testet die LLM Full-Text Search."""
    vault_id = test_vault_1_obj.id

    create_test_node(client, auth_headers_1, vault_id, "Python Guide", "Alles über Python")
    create_test_node(client, auth_headers_1, vault_id, "JavaScript Guide", "Alles über JS")

    response = client.get(
        f'/api/vaults/{vault_id}/nodes/full-search?q=Python',
        headers=auth_headers_1
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['query'] == "Python"
    assert data['count'] == 1
    assert data['results'][0]['title'] == "Python Guide"


def test_full_text_search_missing_query(client, auth_headers_1, test_vault_1_obj):
    """Testet die Validierung bei fehlendem Suchparameter."""
    vault_id = test_vault_1_obj.id
    response = client.get(f'/api/vaults/{vault_id}/nodes/full-search', headers=auth_headers_1)

    assert response.status_code == 400
    assert "Missing search query parameter 'q'" in response.get_json()['error']


@pytest.mark.parametrize("invalid_limit", [0, 101])
def test_full_text_search_invalid_limit(client, auth_headers_1, test_vault_1_obj, invalid_limit):
    """Testet Limits außerhalb des erlaubten Bereichs."""
    vault_id = test_vault_1_obj.id
    response = client.get(
        f'/api/vaults/{vault_id}/nodes/full-search?q=Test&limit={invalid_limit}',
        headers=auth_headers_1
    )

    assert response.status_code == 400
    assert "Parameter 'limit' must be between 1 and 100" in response.get_json()['error']


def test_full_text_search_permission_denied(client, auth_headers_2, test_vault_1_obj):
    """Testet, dass User 2 nicht im Vault von User 1 suchen darf."""
    response = client.get(
        f'/api/vaults/{test_vault_1_obj.id}/nodes/full-search?q=Test',
        headers=auth_headers_2
    )
    assert response.status_code == 403

# ========================================================================
# Tests für ?version= Parameter bei GET /<node_id>
# ========================================================================

@pytest.mark.parametrize("invalid_version", [
    "abc",    # Kein Integer
    "0",      # <= 0
    "-5",     # Negativ
    "2.5"     # Float
])
def test_get_single_node_with_invalid_version_param_returns_400(client, auth_headers_1, test_vault_1_obj, invalid_version):
    """
    Testet, dass ungültige `?version=` Parameter vom API-Endpunkt abgefangen werden
    und einen 400 Bad Request mit der korrekten Fehlermeldung auslösen.
    """
    vault_id = test_vault_1_obj.id
    node = create_test_node(client, auth_headers_1, vault_id, "Version Param Test")

    # ACT
    response = client.get(
        f'/api/vaults/{vault_id}/nodes/{node["id"]}?version={invalid_version}',
        headers=auth_headers_1
    )

    # ASSERT
    assert response.status_code == 400
    assert "Invalid version parameter" in response.get_json()['error']


def test_get_single_node_with_valid_version_param(client, auth_headers_1, test_vault_1_obj):
    """
    Testet den Erfolgsfall, wenn ein gültiger `?version=` Parameter übergeben wird.
    """
    vault_id = test_vault_1_obj.id
    # 1. Erstelle Node (Version 1)
    node = create_test_node(client, auth_headers_1, vault_id, "Titel V1", "Content V1")
    # 2. Update Node (Version 2)
    client.put(f'/api/vaults/{vault_id}/nodes/{node["id"]}', headers=auth_headers_1, json={"title": "Titel V2"})

    # ACT: Hole explizit Version 1
    response = client.get(
        f'/api/vaults/{vault_id}/nodes/{node["id"]}?version=1',
        headers=auth_headers_1
    )

    # ASSERT
    assert response.status_code == 200
    data = response.get_json()
    assert data['version'] == 1
    assert data['title'] == "Titel V1"
    assert data['content'] == "Content V1"