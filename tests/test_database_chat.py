import pytest

# Wir importieren jetzt ALLE Modelle, die wir als `spec` verwenden werden.
# Das macht die Tests robuster gegenüber Änderungen an den echten Klassen.
from backend.models import ChatSession, ChatMessage
from backend import database

def test_list_chat_sessions(test_user_1_obj, test_vault_1_obj):
    """Testet das Auflisten von Chat-Sessions."""
    database.create_chat_session("Session 1", test_vault_1_obj.id, test_user_1_obj.id)
    sessions = database.list_chat_sessions(test_vault_1_obj.id, test_user_1_obj.id)
    assert len(sessions) == 1
    assert sessions[0]['title'] == "Session 1"

def test_get_chat_session_history_not_found(test_user_1_obj):
    """Testet den Abruf einer nicht existierenden Session."""
    with pytest.raises(ValueError, match="Chat session with ID not-found-id not found."):
        database.get_chat_session_history("not-found-id", test_user_1_obj.id)

def test_get_chat_session_history_permission_denied(test_user_1_obj, test_user_2_obj, test_vault_2_obj):
    """Testet, dass User 1 nicht auf die Session von User 2 zugreifen kann."""
    session_user2 = database.create_chat_session("Secret Chat", test_vault_2_obj.id, test_user_2_obj.id)
    with pytest.raises(PermissionError, match="You do not have permission to access this chat session."):
        database.get_chat_session_history(session_user2.id, test_user_1_obj.id)

def test_delete_chat_session_not_found(test_user_1_obj):
    """Testet das Löschen einer nicht existierenden Session."""
    with pytest.raises(ValueError):
        database.delete_chat_session("not-found-id", test_user_1_obj.id)

def test_delete_chat_session_permission_denied(test_user_1_obj, test_user_2_obj, test_vault_2_obj):
    """Testet, dass User 1 nicht die Session von User 2 löschen kann."""
    session_user2 = database.create_chat_session("Secret Chat", test_vault_2_obj.id, test_user_2_obj.id)
    with pytest.raises(PermissionError):
        database.delete_chat_session(session_user2.id, test_user_1_obj.id)

# tests/test_database_chat.py
# Stellen Sie sicher, dass 'database', 'ChatSession' und 'db_session' verfügbar sind.

def test_delete_chat_session_success(test_user_1_obj, test_vault_1_obj, db_session):
    """
    Testet das erfolgreiche Löschen einer Chat-Sitzung.
    """
    # 1. ARRANGE: Erstelle eine Session, die wir löschen können.
    session = database.create_chat_session(
        title="Session to be deleted",
        vault_id=test_vault_1_obj.id,
        owner_id=test_user_1_obj.id
    )
    session_id = session.id
    # Sicherstellen, dass sie in der DB ist
    assert db_session.session.get(ChatSession, session_id) is not None

    # 2. ACT: Rufe die Löschfunktion auf.
    database.delete_chat_session(session_id=session_id, user_id=test_user_1_obj.id)

    # 3. ASSERT: Überprüfe, ob die Session aus der DB entfernt wurde.
    assert db_session.session.get(ChatSession, session_id) is None

def test_add_chat_message_success(test_user_1_obj, test_vault_1_obj, db_session):
    """
    Testet das erfolgreiche Hinzufügen einer Chat-Nachricht zu einer Session.
    """
    # 1. ARRANGE: Erstelle eine Session, zu der wir eine Nachricht hinzufügen können.
    session = database.create_chat_session(
        title="Session with new message",
        vault_id=test_vault_1_obj.id,
        owner_id=test_user_1_obj.id
    )
    db_session.session.commit() # Commit, um die Session persistent zu machen

    # 2. ACT: Füge eine Nachricht hinzu.
    new_message = database.add_chat_message(
        session_id=session.id,
        role="user",
        content="Hello, world!",
        author_id=test_user_1_obj.id
    )
    db_session.session.commit() # Commit, um die Nachricht zu speichern

    # 3. ASSERT: Überprüfe, ob die Nachricht korrekt erstellt wurde.
    assert new_message.id is not None
    assert new_message.role == "user"
    assert new_message.content == "Hello, world!"
    assert new_message.session_id == session.id

    # Optional: Überprüfe, ob die Nachricht in der Session-Beziehung erscheint
    refreshed_session = db_session.session.get(ChatSession, session.id)
    assert len(refreshed_session.messages) == 1
    assert refreshed_session.messages[0].content == "Hello, world!"

def test_add_chat_message_with_context_versions(test_user_1_obj, test_vault_1_obj, db_session):
    """
    Testet das Hinzufügen einer Chat-Nachricht mit Verknüpfungen zu Kontext-Versionen.
    Dies deckt die Many-to-Many-Beziehung ab.
    """
    # 1. ARRANGE
    # a) Erstelle eine Chat-Session
    session = database.create_chat_session(
        title="Session with Context",
        vault_id=test_vault_1_obj.id,
        owner_id=test_user_1_obj.id
    )
    db_session.session.commit()

    # b) Erstelle zwei Nodes, deren Versionen wir als Kontext verwenden wollen.
    context_node1 = database.create_node(
        "Context Node 1", "Content for context 1", None, test_vault_1_obj.id, test_user_1_obj.id
    )
    context_node2 = database.create_node(
        "Context Node 2", "Content for context 2", None, test_vault_1_obj.id, test_user_1_obj.id
    )

    # c) Hole die tatsächlichen Version-Objekte dieser Nodes.
    # Wir können hier unsere bereits getestete Funktion verwenden!
    versions_to_link = database.get_versions_for_node_ids(
        [context_node1.id, context_node2.id],
        test_vault_1_obj.id,
        test_user_1_obj.id
    )
    assert len(versions_to_link) == 2

    # 2. ACT: Füge eine Nachricht hinzu und übergebe die Versionen als Kontext.
    new_message = database.add_chat_message(
        session_id=session.id,
        role="user",
        content="This is my question with context.",
        author_id=test_user_1_obj.id,
        context_versions=versions_to_link  # Hier übergeben wir den Kontext
    )
    db_session.session.commit()

    # 3. ASSERT: Überprüfe, ob die Verknüpfung korrekt erstellt wurde.
    # Holen die Nachricht frisch aus der DB, um sicherzustellen, dass die Beziehung geladen wird.
    retrieved_message = db_session.session.get(ChatMessage, new_message.id)

    assert retrieved_message is not None
    # Die entscheidende Prüfung: Hat die Nachricht 2 verknüpfte Kontext-Versionen?
    assert len(retrieved_message.context_versions) == 2

    # Überprüfe, ob es die richtigen Versionen sind.
    linked_version_contents = sorted([v.content for v in retrieved_message.context_versions])
    assert linked_version_contents == ["Content for context 1", "Content for context 2"]

def test_add_chat_message_with_different_versions_of_same_node(test_user_1_obj, test_vault_1_obj, db_session):
    """
    Testet, ob zwei verschiedene Nachrichten korrekt mit zwei unterschiedlichen
    Versionen DESSELBEN Nodes verknüpft werden können.
    """
    # 1. ARRANGE
    # a) Erstelle eine Chat-Session und einen Node.
    session = database.create_chat_session("Versioning Test", test_vault_1_obj.id, test_user_1_obj.id)
    node = database.create_node(
        "My Document", "Initial content (V1)", None, test_vault_1_obj.id, test_user_1_obj.id
    )

    # b) Hole die erste Version (V1)
    version1 = database.get_versions_for_node_ids([node.id], test_vault_1_obj.id, test_user_1_obj.id)[0]
    assert version1.version == 1

    # c) Erstelle eine zweite Version (V2) durch ein Update.
    database.update_node(
        node.id, test_vault_1_obj.id, test_user_1_obj.id, content="Updated content (V2)"
    )
    # Hole die zweite Version
    version2 = database.get_versions_for_node_ids([node.id], test_vault_1_obj.id, test_user_1_obj.id)[0]
    assert version2.version == 2
    assert version1.id != version2.id # Wichtig: Es sind zwei verschiedene Einträge in der `versions`-Tabelle

    # 2. ACT
    # a) Erstelle eine Nachricht mit dem Kontext von Version 1.
    message1 = database.add_chat_message(
        session_id=session.id,
        role="user",
        content="Question about V1",
        author_id=test_user_1_obj.id,
        context_versions=[version1]
    )

    # b) Erstelle eine zweite Nachricht mit dem Kontext von Version 2.
    message2 = database.add_chat_message(
        session_id=session.id,
        role="user",
        content="Question about V2",
        author_id=test_user_1_obj.id,
        context_versions=[version2]
    )
    db_session.session.commit()

    # 3. ASSERT
    # a) Überprüfe die erste Nachricht
    retrieved_message1 = db_session.session.get(ChatMessage, message1.id)
    assert len(retrieved_message1.context_versions) == 1
    assert retrieved_message1.context_versions[0].id == version1.id
    assert retrieved_message1.context_versions[0].content == "Initial content (V1)"

    # b) Überprüfe die zweite Nachricht
    retrieved_message2 = db_session.session.get(ChatMessage, message2.id)
    assert len(retrieved_message2.context_versions) == 1
    assert retrieved_message2.context_versions[0].id == version2.id
    assert retrieved_message2.context_versions[0].content == "Updated content (V2)"

    # c) Gegenprobe: Sicherstellen, dass message1 nicht mit V2 verknüpft ist
    assert retrieved_message1.context_versions[0].id != version2.id