# migrate_data.py
import os
import sys

# --- WICHTIG: Pfad-Korrektur ---
# Damit dieses Skript die Module aus 'backend' findet (z.B. models),
# fügen wir das Projekt-Hauptverzeichnis zum Python-Pfad hinzu.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print(f"Project root added to path: {project_root}")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Lade die Modelle, die wir migrieren wollen
from backend.models import db, User, Vault, Node, Version, ChatSession, ChatMessage, chat_message_context

print("Models imported successfully.")

# --- KONFIGURATION ---
load_dotenv(os.path.join(project_root, '.env'))

# Quelle: Die alte SQLite-Datenbank
basedir = os.path.abspath(os.path.dirname(__file__))
SQLITE_URI = 'sqlite:///' + os.path.join(basedir,
                                         'knowledge_base.db')  # Passe den Namen an, falls deine DB anders heißt

# Ziel: Die neue PostgreSQL-Datenbank (aus der .env-Datei)
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
POSTGRES_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- VERBINDUNGEN AUFBAUEN ---
print(f"Connecting to SOURCE: {SQLITE_URI}")
source_engine = create_engine(SQLITE_URI)
SourceSession = sessionmaker(bind=source_engine)

print(f"Connecting to TARGET: postgresql://{DB_USER}:...@{DB_HOST}:{DB_PORT}/{DB_NAME}")
target_engine = create_engine(POSTGRES_URI)
TargetSession = sessionmaker(bind=target_engine)


# --- DER MIGRATIONS-PROZESS ---
def migrate_data():
    source_session = SourceSession()
    target_session = TargetSession()

    try:
        # Die Reihenfolge ist extrem wichtig wegen der Foreign-Key-Beziehungen!
        # Zuerst Tabellen ohne Abhängigkeiten, dann die, die auf sie verweisen.

        # 1. Users
        print("\nMigrating Users...")
        users = source_session.query(User).all()
        for user in users:
            new_user = User(
                id=user.id,  # WICHTIG: IDs beibehalten!
                username=user.username,
                display_name=user.display_name,
                password_hash=user.password_hash,
                user_type=user.user_type,
                is_admin=user.is_admin,
                created_at=user.created_at
            )
            target_session.add(new_user)
        target_session.commit()
        print(f"-> Migrated {len(users)} users.")

        # 2. Vaults
        print("\nMigrating Vaults...")
        vaults = source_session.query(Vault).all()
        for vault in vaults:
            new_vault = Vault(
                id=vault.id,
                name=vault.name,
                created_at=vault.created_at,
                owner_id=vault.owner_id
            )
            target_session.add(new_vault)
        target_session.commit()
        print(f"-> Migrated {len(vaults)} vaults.")

        # 3. Nodes
        print("\nMigrating Nodes...")
        nodes = source_session.query(Node).all()
        for node in nodes:
            new_node = Node(
                id=node.id,
                current_version=node.current_version,
                icon=node.icon,
                parent_id=node.parent_id,
                vault_id=node.vault_id
            )
            target_session.add(new_node)
        target_session.commit()
        print(f"-> Migrated {len(nodes)} nodes.")

        # 4. Versions
        print("\nMigrating Versions...")
        versions = source_session.query(Version).all()
        for version in versions:
            new_version = Version(
                id=version.id,
                title=version.title,
                version=version.version,
                content=version.content,
                timestamp=version.timestamp,
                node_id=version.node_id,
                author_id=version.author_id
            )
            target_session.add(new_version)
        target_session.commit()
        print(f"-> Migrated {len(versions)} versions.")

        # 5. ChatSessions
        print("\nMigrating ChatSessions...")
        sessions = source_session.query(ChatSession).all()
        for session in sessions:
            new_session = ChatSession(
                id=session.id,
                title=session.title,
                created_at=session.created_at,
                vault_id=session.vault_id,
                owner_id=session.owner_id
            )
            target_session.add(new_session)
        target_session.commit()
        print(f"-> Migrated {len(sessions)} chat sessions.")

        # 6. ChatMessages
        print("\nMigrating ChatMessages...")
        messages = source_session.query(ChatMessage).all()
        for message in messages:
            new_message = ChatMessage(
                id=message.id,
                session_id=message.session_id,
                role=message.role,
                content=message.content,
                timestamp=message.timestamp,
                author_id=message.author_id,
                llm_model_source=message.llm_model_source,
                status=message.status,
                sort_order=message.sort_order
            )
            target_session.add(new_message)
        target_session.commit()
        print(f"-> Migrated {len(messages)} chat messages.")

        # 7. Many-to-Many Relationships (chat_message_context)
        print("\nMigrating Chat Message Context (Many-to-Many)...")
        # Hier lesen wir die Beziehungen direkt aus der Quell-DB
        count = 0
        all_source_messages = source_session.query(ChatMessage).all()
        for source_message in all_source_messages:
            if source_message.context_versions:
                # Finde die entsprechende Nachricht in der Ziel-DB
                target_message = target_session.get(ChatMessage, source_message.id)
                for source_version in source_message.context_versions:
                    # Finde die entsprechende Version in der Ziel-DB
                    target_version = target_session.get(Version, source_version.id)
                    # Füge die Beziehung hinzu
                    target_message.context_versions.append(target_version)
                    count += 1
        target_session.commit()
        print(f"-> Migrated {count} context links.")

        print("\n\n✅✅✅ MIGRATION COMPLETE! ✅✅✅")

    except Exception as e:
        print(f"\n🔥🔥🔥 AN ERROR OCCURRED: {e} 🔥🔥🔥")
        target_session.rollback()
    finally:
        source_session.close()
        target_session.close()
        print("Sessions closed.")


if __name__ == '__main__':
    migrate_data()