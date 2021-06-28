import pytest
import sirius_sdk
import sqlalchemy
import databases

from app.db.database import database, metadata
from app.db.models import users, agents
from app.settings import TEST_DATABASE_NAME, TEST_SQLALCHEMY_DATABASE_URL


@pytest.fixture()
def random_me() -> (str, str, str):
    """
    Generate Random identifications

    :return: did, verkey, privkey
    """
    pub_key, priv_key = sirius_sdk.encryption.ed25519.create_keypair()
    did = sirius_sdk.encryption.did_from_verkey(pub_key)
    return sirius_sdk.encryption.bytes_to_b58(did), sirius_sdk.encryption.bytes_to_b58(pub_key), \
           sirius_sdk.encryption.bytes_to_b58(priv_key)


@pytest.fixture()
async def test_database():
    await database.connect()
    try:
        await database.execute(f'drop database if exists {TEST_DATABASE_NAME};')
        await database.execute(f'create database {TEST_DATABASE_NAME};')
    finally:
        await database.disconnect()
    test_engine = sqlalchemy.create_engine(TEST_SQLALCHEMY_DATABASE_URL)
    metadata.create_all(test_engine, tables=[users, agents])
    test_database = databases.Database(TEST_SQLALCHEMY_DATABASE_URL)
    await test_database.connect()
    try:
        yield test_database
    finally:
        await test_database.disconnect()
