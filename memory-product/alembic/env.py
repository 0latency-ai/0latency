import os
from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

# Choose DB URL based on -x env=staging flag
x_args = context.get_x_argument(as_dictionary=True)
env_target = x_args.get('env', 'prod')

if env_target == 'staging':
    db_url = os.environ.get('STAGING_DATABASE_URL')
elif env_target == 'prod':
    db_url = os.environ.get('DATABASE_URL')
else:
    raise RuntimeError(f"Unknown env: {env_target}")

if not db_url:
    raise RuntimeError(f"DB URL not set for env={env_target}")

config.set_main_option('sqlalchemy.url', db_url)

target_metadata = None  # no autogenerate; manual revisions only

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table='alembic_version',
            version_table_schema='memory_service',
        )
        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()
