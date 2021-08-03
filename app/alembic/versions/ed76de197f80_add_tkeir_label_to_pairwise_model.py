"""add tkeir label to pairwise model

Revision ID: ed76de197f80
Revises: c0425d8da0c1
Create Date: 2021-08-03 16:19:27.327703

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ed76de197f80'
down_revision = 'c0425d8da0c1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('pairwises', sa.Column('their_label', sa.String, nullable=True, index=True))


def downgrade():
    op.drop_column('pairwises', 'their_label')
