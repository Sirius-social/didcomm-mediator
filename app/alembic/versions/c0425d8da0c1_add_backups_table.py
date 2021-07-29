"""add backups table

Revision ID: c0425d8da0c1
Revises: b4a83593d7d9
Create Date: 2021-07-27 08:40:12.181812

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c0425d8da0c1'
down_revision = 'b4a83593d7d9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'backups',
        sa.Column("id", sa.INTEGER, primary_key=True, autoincrement=True),
        sa.Column("binary", sa.LargeBinary),
        sa.Column("description", sa.String, index=True),
        sa.Column("context", sa.JSON, nullable=True),
    )


def downgrade():
    op.drop_table('backups')
