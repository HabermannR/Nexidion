import json
import click
from backend.models import db, User, UserType, ConnectorInstallation
from backend.ingestion import connector_registry
from backend.services.ingestion_service import run_connector
from backend.services.legacy_image_conversion import convert_legacy_images

def register_commands(app):
    app.cli.add_command(create_admin)
    app.cli.add_command(create_llm_agent)
    app.cli.add_command(list_connectors)
    app.cli.add_command(register_connector)
    app.cli.add_command(run_ingestion)
    app.cli.add_command(convert_legacy_image_refs)

@click.command('create-admin')
@click.argument('username')
@click.argument('password')
@click.option('--display-name', default=None)
def create_admin(username, password, display_name):
    """Creates a new administrator user."""
    if User.query.filter_by(username=username).first():
        click.echo(f"Error: user '{username}' already exists.")
        return
    user = User(
        username=username,
        display_name=display_name or username.capitalize(),
        user_type=UserType.HUMAN,
        is_admin=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f"Administrator '{username}' created (ID: {user.id}).")

@click.command('create-llm-agent')
def create_llm_agent():
    """Creates the LLM agent user if it does not already exist."""
    existing = User.query.filter_by(user_type=UserType.LLM_ASSISTANT).first()
    if existing:
        click.echo(f"LLM agent already exists (ID: {existing.id}).")
        return
    agent = User(
        username='default-llm',
        display_name='Nexidion AI',
        user_type=UserType.LLM_ASSISTANT,
        is_admin=False,
    )
    db.session.add(agent)
    db.session.commit()
    click.echo(f"LLM agent created (ID: {agent.id}).")


@click.command('list-connectors')
def list_connectors():
    """List built-in and installed connector plugins."""
    for name in connector_registry.names():
        connector = connector_registry.get(name)
        click.echo(f"{name}: {', '.join(sorted(connector.capabilities))}")


@click.command('register-connector')
@click.argument('vault_id', type=int)
@click.argument('plugin_name')
@click.argument('name')
@click.option('--mode', type=click.Choice(['read', 'ingest', 'both']), default='ingest')
@click.option('--config-json', default='{}', help='Non-secret connector configuration as JSON.')
@click.option('--credential-ref', default=None, help='Reference to an environment/secret-store credential.')
@click.option('--user-id', type=int, required=True)
def register_connector(vault_id, plugin_name, name, mode, config_json, credential_ref, user_id):
    """Register a connector without embedding credentials in the database."""
    connector_registry.get(plugin_name)
    config = json.loads(config_json)
    row = ConnectorInstallation(vault_id=vault_id, plugin_name=plugin_name, name=name,
                                mode=mode, config=config, credential_ref=credential_ref,
                                created_by_id=user_id)
    db.session.add(row)
    db.session.commit()
    click.echo(row.id)


@click.command('run-ingestion')
@click.argument('connector_id')
@click.option('--user-id', type=int, required=True)
@click.option('--executor-id', type=int, default=None)
def run_ingestion(connector_id, user_id, executor_id):
    """Run one connector synchronously; portable worker/automation primitive."""
    result = run_connector(connector_id, user_id, executor_id)
    click.echo(json.dumps(result.stats, sort_keys=True))


@click.command('convert-legacy-images')
@click.argument('legacy_folder', type=click.Path(exists=True, file_okay=False))
@click.option('--apply', 'apply_changes', is_flag=True,
              help='Create managed assets and new current node versions. Default is dry-run.')
def convert_legacy_image_refs(legacy_folder, apply_changes):
    """Convert /api/image references to vault-scoped managed assets."""
    report = convert_legacy_images(legacy_folder, apply=apply_changes)
    click.echo(json.dumps(report, indent=2, sort_keys=True))
