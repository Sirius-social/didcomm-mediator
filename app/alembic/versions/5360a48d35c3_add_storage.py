"""add_storage

Revision ID: 5360a48d35c3
Revises: ed76de197f80
Create Date: 2022-10-06 15:58:18.507193

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5360a48d35c3'
down_revision = 'ed76de197f80'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'key_value_storage',
        sa.Column('id', sa.INTEGER, primary_key=True, autoincrement=True),
        sa.Column("namespace", sa.String, index=True),
        sa.Column("key", sa.String, index=True),
        sa.Column("value", sa.String, nullable=True),
    )


def downgrade():
    op.drop_table('key_value_storage')
