"""init

Revision ID: 4194f8c4ae77
Revises: 
Create Date: 2021-06-28 01:37:19.461275

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4194f8c4ae77'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.String, primary_key=True, index=True),
        sa.Column('username', sa.String, unique=True, index=True),
        sa.Column('hashed_password', sa.String),
        sa.Column('is_active', sa.Boolean, default=True),
    )
    op.create_table(
        'agents',
        sa.Column('id', sa.String, primary_key=True, index=True),
        sa.Column('did', sa.String, unique=True, index=True),
        sa.Column('verkey', sa.String, index=True),
        sa.Column('metadata', sa.JSON, nullable=True),
        sa.Column('fcm_device_id', sa.String, nullable=True, index=True),
    )
    op.create_table(
        'pairwises',
        sa.Column('their_did', sa.String, primary_key=True, index=True),
        sa.Column('their_verkey', sa.String, index=True),
        sa.Column('my_did', sa.String, index=True),
        sa.Column('my_verkey', sa.String, index=True),
        sa.Column('metadata', sa.JSON, nullable=True)
    )
    op.create_table(
        'endpoints',
        sa.Column('uid', sa.String, primary_key=True),
        sa.Column('verkey', sa.String, index=True),
        sa.Column('agent_id', sa.String, index=True, nullable=True),
        sa.Column('redis_pub_sub', sa.String),
        sa.Column('fcm_device_id', sa.String, nullable=True, index=True),
    )
    op.create_table(
        'routing_keys',
        sa.Column('id', sa.INTEGER, primary_key=True, autoincrement=True),
        sa.Column('key', sa.String, index=True),
        sa.Column('endpoint_uid', sa.String, index=True),
    )


def downgrade():
    op.drop_table('users')
    op.drop_table('agents')
    op.drop_table('pairwises')
    op.drop_table('endpoints')
    op.drop_table('routing_keys')
