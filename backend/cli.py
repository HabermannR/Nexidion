import click
from backend.models import db, User, UserType

def register_commands(app):
    app.cli.add_command(create_admin)
    app.cli.add_command(create_llm_agent)

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