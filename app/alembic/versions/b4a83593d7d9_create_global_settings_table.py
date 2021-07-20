"""create global_settings table

Revision ID: b4a83593d7d9
Revises: 4194f8c4ae77
Create Date: 2021-07-20 08:29:08.056093

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4a83593d7d9'
down_revision = '4194f8c4ae77'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'global_settings',
        sa.Column('id', sa.INTEGER, primary_key=True, autoincrement=True),
        sa.Column("content", sa.JSON),
    )


def downgrade():
    op.drop_table('global_settings')
