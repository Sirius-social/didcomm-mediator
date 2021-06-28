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
        'companies',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('label', sa.String, index=True),
    )
    op.create_table(
        'users',
        sa.Column('id', sa.String, primary_key=True, index=True),
        sa.Column('username', sa.String, unique=True, index=True),
        sa.Column('hashed_password', sa.String),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('company_id', sa.Integer, sa.ForeignKey('companies.id')),
    )
    op.create_table(
        'agents',
        sa.Column('id', sa.String, primary_key=True, index=True),
        sa.Column('did', sa.String, unique=True, index=True),
        sa.Column('verkey', sa.String, index=True),
        sa.Column('metadata', sa.JSON)
    )


def downgrade():
    op.drop_table('companies')
    op.drop_table('users')
    op.drop_table('agents')
