import pytest

from backend.services import chat_service
from backend.models import User, Vault, ChatSession, ChatMessage


def test_list_sessions(test_user_1_obj: User, test_vault_1_obj: Vault):
    """
    Testet das Auflisten von Chat-Sessions über den chat_service.
    """
    # 1. Setup: Erstelle eine Session über den Service.
    #    Das ist besser, als die DB direkt zu manipulieren, da wir so
    #    die Logik von `create_new_session` gleich mit abdecken.
    #    Der Standardtitel laut deinem Code ist "New Chat".
    chat_service.create_new_session(
        vault_id=test_vault_1_obj.id,
        user_id=test_user_1_obj.id
    )

    # 2. Ausführung: Rufe die zu testende Funktion auf.
    sessions = chat_service.list_sessions(
        vault_id=test_vault_1_obj.id,
        user_id=test_user_1_obj.id
    )

    # 3. Überprüfung: Die Assertions sind fast identisch.
    assert len(sessions) == 1
    assert isinstance(sessions[0], dict)  # Der Service gibt Dictionaries zurück
    assert sessions[0]['title'] == "New Chat"
    assert sessions[0]['vault_id'] == test_vault_1_obj.id
    assert sessions[0]['owner_id'] == test_user_1_obj.id


def test_get_session_history_not_found(test_user_1_obj: User):
    """
    Testet den Abruf einer nicht existierenden Session über den chat_service.
    """
    # Die Logik hier bleibt fast gleich, da der Service den gleichen Fehler auslöst.
    # Wir rufen nur die neue Funktion auf.

    # 1. Setup: (Keines nötig, wir wollen ja einen Fehler provozieren)

    # 2. Ausführung & Überprüfung:
    with pytest.raises(ValueError, match="Chat session with ID not-found-id not found."):
        chat_service.get_session_history(
            session_id="not-found-id",
            user_id=test_user_1_obj.id
        )


def test_get_session_history_permission_denied(test_user_1_obj: User, test_user_2_obj: User, test_vault_2_obj: Vault):
    """Testet, dass User 1 nicht auf die Session von User 2 zugreifen kann."""
    # 1. ARRANGE: Erstelle eine Session für User 2 über den Service
    session_user2 = chat_service.create_new_session(
        vault_id=test_vault_2_obj.id,
        user_id=test_user_2_obj.id
    )

    # Annahme: User 1 hat keinen Zugriff auf test_vault_2_obj.
    # Der Fehler sollte von `_verify_vault_access` kommen.
    # Wir nehmen an, dieser wirft einen PermissionError.
    with pytest.raises(PermissionError, match="You do not have permission to access this vault."):
        # 2. ACT & ASSERT
        chat_service.get_session_history(session_user2.id, test_user_1_obj.id)


def test_delete_session_not_found(test_user_1_obj: User):
    """Testet das Löschen einer nicht existierenden Session über den Service."""
    # Der Service wirft einen ValueError, wenn die Session nicht gefunden wird.
    with pytest.raises(ValueError, match="Chat session with ID not-found-id not found."):
        chat_service.delete_session("not-found-id", test_user_1_obj.id)


def test_delete_session_permission_denied(test_user_1_obj: User, test_user_2_obj: User, test_vault_2_obj: Vault):
    """Testet, dass User 1 nicht die Session von User 2 löschen kann."""
    # 1. ARRANGE: Erstelle eine Session für User 2
    session_user2 = chat_service.create_new_session(
        vault_id=test_vault_2_obj.id,
        user_id=test_user_2_obj.id
    )

    # 2. ACT & ASSERT
    with pytest.raises(PermissionError, match="You do not have permission to access this vault."):
        chat_service.delete_session(session_user2.id, test_user_1_obj.id)


def test_delete_session_success(test_user_1_obj: User, test_vault_1_obj: Vault, db_session):
    """Testet das erfolgreiche Löschen einer Chat-Session über den Service."""
    # 1. ARRANGE: Erstelle eine Session über den Service
    session = chat_service.create_new_session(
        vault_id=test_vault_1_obj.id,
        user_id=test_user_1_obj.id
    )
    session_id = session.id
    assert db_session.session.get(ChatSession, session_id) is not None

    # 2. ACT: Rufe die Löschfunktion im Service auf
    chat_service.delete_session(session_id=session_id, user_id=test_user_1_obj.id)

    # 3. ASSERT: Überprüfe, ob die Session aus der DB entfernt wurde
    assert db_session.session.get(ChatSession, session_id) is None


def test_update_session_title_success(test_user_1_obj, test_vault_1_obj, db_session):
    """
    Testet, ob der Titel einer Session erfolgreich aktualisiert und gespeichert wird.
    """
    # 1. ARRANGE
    # Erstelle eine Session in der DB
    session = ChatSession(
        vault_id=test_vault_1_obj.id,
        owner_id=test_user_1_obj.id,
        title="Alter Titel"
    )
    db_session.session.add(session)
    db_session.session.commit()

    new_title = "Brandneuer Titel"

    # 2. ACT
    # Rufe die Service-Funktion direkt auf
    updated_session = chat_service.update_session_title(
        session_id=session.id,
        user_id=test_user_1_obj.id,
        new_title=new_title
    )

    # 3. ASSERT
    # Überprüfe das zurückgegebene Objekt
    assert isinstance(updated_session, ChatSession)
    assert updated_session.title == new_title
    assert updated_session.id == session.id

    # Überprüfe den Zustand in der Datenbank explizit
    db_session.session.refresh(session)
    assert session.title == new_title


def test_update_session_title_raises_error_for_wrong_user(test_user_1_obj, test_user_2_obj, test_vault_1_obj, db_session):
    """
    Testet, ob ein PermissionError ausgelöst wird, wenn ein nicht berechtigter User
    versucht, den Titel zu ändern. Dies testet indirekt, dass _verify_session_access
    korrekt aufgerufen wird.
    """
    # 1. ARRANGE
    # Session gehört User 1
    session = ChatSession(
        vault_id=test_vault_1_obj.id,
        owner_id=test_user_1_obj.id,
        title="Titel von User 1"
    )
    db_session.session.add(session)
    db_session.session.commit()

    # 2. ACT & 3. ASSERT
    # User 2 versucht den Titel zu ändern
    with pytest.raises(PermissionError):
        chat_service.update_session_title(
            session_id=session.id,
            user_id=test_user_2_obj.id, # <-- Falscher User
            new_title="Hacking Versuch"
        )


def test_get_session_history_success_and_sorted(test_user_1_obj, test_vault_1_obj, db_session):
    """
    Testet, ob der Verlauf einer Session korrekt und nach `sort_order` sortiert zurückgegeben wird.
    """
    # 1. ARRANGE
    session = ChatSession(
        vault_id=test_vault_1_obj.id,
        owner_id=test_user_1_obj.id
    )
    # Erstelle Nachrichten in "falscher" Reihenfolge, um die Sortierung zu testen
    msg3 = ChatMessage(session=session, role='assistant', content='Antwort', author_id=99, sort_order=3)
    msg1 = ChatMessage(session=session, role='user', content='Frage', author_id=test_user_1_obj.id, sort_order=1)
    msg2 = ChatMessage(session=session, role='assistant', content='Präzisierende Frage', author_id=99, sort_order=2)

    db_session.session.add_all([session, msg3, msg1, msg2])
    db_session.session.commit()

    # 2. ACT
    history = chat_service.get_session_history(
        session_id=session.id,
        user_id=test_user_1_obj.id
    )

    # 3. ASSERT
    assert isinstance(history, dict)
    assert history['id'] == session.id
    assert 'messages' in history

    messages = history['messages']
    assert len(messages) == 3

    # Überprüfe die korrekte Sortierung basierend auf `sort_order`
    assert messages[0]['content'] == 'Frage'
    assert messages[0]['sort_order'] == 1

    assert messages[1]['content'] == 'Präzisierende Frage'
    assert messages[1]['sort_order'] == 2

    assert messages[2]['content'] == 'Antwort'
    assert messages[2]['sort_order'] == 3


def test_get_session_history_empty_session(test_user_1_obj, test_vault_1_obj, db_session):
    """
    Testet, ob eine leere Nachrichtenliste für eine neue Session zurückgegeben wird.
    """
    # 1. ARRANGE
    session = ChatSession(
        vault_id=test_vault_1_obj.id,
        owner_id=test_user_1_obj.id
    )
    db_session.session.add(session)
    db_session.session.commit()

    # 2. ACT
    history = chat_service.get_session_history(
        session_id=session.id,
        user_id=test_user_1_obj.id
    )

    # 3. ASSERT
    assert history['id'] == session.id
    assert isinstance(history['messages'], list)
    assert len(history['messages']) == 0


def test_get_session_history_raises_error_for_wrong_user(test_user_1_obj, test_user_2_obj, test_vault_1_obj,
                                                         db_session):
    """
    Testet, ob ein PermissionError ausgelöst wird, wenn ein nicht berechtigter User
    versucht, den Verlauf abzurufen.
    """
    # 1. ARRANGE
    # Session gehört User 1
    session = ChatSession(
        vault_id=test_vault_1_obj.id,
        owner_id=test_user_1_obj.id
    )
    db_session.session.add(session)
    db_session.session.commit()

    # 2. ACT & 3. ASSERT
    # User 2 versucht, den Verlauf abzurufen
    with pytest.raises(PermissionError):
        chat_service.get_session_history(
            session_id=session.id,
            user_id=test_user_2_obj.id  # <-- Falscher User
        )