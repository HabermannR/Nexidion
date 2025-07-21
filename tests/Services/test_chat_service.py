import pytest

from backend.services import chat_service

from backend.models import User, Vault, ChatSession


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


