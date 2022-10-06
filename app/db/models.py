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
    sqlalchemy.Column("metadata", sqlalchemy.JSON, nullable=True),
    sqlalchemy.Column("fcm_device_id", sqlalchemy.String, nullable=True, index=True)
)


pairwises = sqlalchemy.Table(
    'pairwises',
    metadata,
    sqlalchemy.Column("their_did", sqlalchemy.String, primary_key=True),
    sqlalchemy.Column("their_verkey", sqlalchemy.String, index=True),
    sqlalchemy.Column("my_did", sqlalchemy.String, index=True),
    sqlalchemy.Column("my_verkey", sqlalchemy.String, index=True),
    sqlalchemy.Column("metadata", sqlalchemy.JSON),
    sqlalchemy.Column("their_label", sqlalchemy.String, nullable=True, index=True),
)


endpoints = sqlalchemy.Table(
    'endpoints',
    metadata,
    sqlalchemy.Column("uid", sqlalchemy.String, primary_key=True),
    sqlalchemy.Column("verkey", sqlalchemy.String, index=True),
    sqlalchemy.Column("agent_id", sqlalchemy.String, index=True, nullable=True),
    sqlalchemy.Column("redis_pub_sub", sqlalchemy.String),
    sqlalchemy.Column("fcm_device_id", sqlalchemy.String, nullable=True, index=True)
)


routing_keys = sqlalchemy.Table(
    'routing_keys',
    metadata,
    sqlalchemy.Column("id", sqlalchemy.INTEGER, primary_key=True, autoincrement=True),
    sqlalchemy.Column("key", sqlalchemy.String, index=True),
    sqlalchemy.Column("endpoint_uid", sqlalchemy.String, index=True),
)


global_settings = sqlalchemy.Table(
    'global_settings',
    metadata,
    sqlalchemy.Column("id", sqlalchemy.INTEGER, primary_key=True, autoincrement=True),
    sqlalchemy.Column("content", sqlalchemy.JSON)
)


backups = sqlalchemy.Table(
    'backups',
    metadata,
    sqlalchemy.Column("id", sqlalchemy.INTEGER, primary_key=True, autoincrement=True),
    sqlalchemy.Column("binary", sqlalchemy.LargeBinary),
    sqlalchemy.Column("description", sqlalchemy.String, index=True),
    sqlalchemy.Column("context", sqlalchemy.JSON, nullable=True),
)


key_value_storage = sqlalchemy.Table(
    'key_value_storage',
    metadata,
    sqlalchemy.Column("id", sqlalchemy.INTEGER, primary_key=True, autoincrement=True),
    sqlalchemy.Column("namespace", sqlalchemy.String, index=True),
    sqlalchemy.Column("key", sqlalchemy.String, index=True),
    sqlalchemy.Column("value", sqlalchemy.String, nullable=True),
)
