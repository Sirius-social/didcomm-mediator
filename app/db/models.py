import sqlalchemy

from .database import metadata


users = sqlalchemy.Table(
    "users",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.String, primary_key=True),
    sqlalchemy.Column("username", sqlalchemy.String, unique=True, index=True),
    sqlalchemy.Column("hashed_password", sqlalchemy.String),
    sqlalchemy.Column("is_active", sqlalchemy.Boolean, default=True)
)


agents = sqlalchemy.Table(
    "agents",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.String, primary_key=True),
    sqlalchemy.Column("did", sqlalchemy.String, unique=True, index=True),
    sqlalchemy.Column("verkey", sqlalchemy.String, index=True),
    sqlalchemy.Column("metadata", sqlalchemy.JSON, nullable=True)
)
