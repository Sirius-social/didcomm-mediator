import sirius_sdk
import sqlalchemy
import databases

from databases import Database
from app.db.database import database, metadata
from app.db.models import users, agents, pairwises
from app.settings import TEST_DATABASE_NAME, TEST_SQLALCHEMY_DATABASE_URL
from app.core.did import MediatorDID
from app.core.crypto import MediatorCrypto
from app.core.pairwise import MediatorPairwiseList
from app.settings import RELAY_KEYPAIR, TEST_SQLALCHEMY_DATABASE_URL


def override_sirius_sdk():
    sirius_sdk.init(
        crypto=MediatorCrypto(*RELAY_KEYPAIR),
        did=MediatorDID(db=Database(TEST_SQLALCHEMY_DATABASE_URL)),
        pairwise_storage=MediatorPairwiseList(db=Database(TEST_SQLALCHEMY_DATABASE_URL))
    )


async def allocate_test_database():
    """Create and prepare test database to inject to testable code

    """
    # connect to postgres server to prepare test database
    await database.connect()
    try:
        # Create empty test database
        await database.execute(f'drop database if exists {TEST_DATABASE_NAME};')
        await database.execute(f'create database {TEST_DATABASE_NAME};')
    finally:
        await database.disconnect()
    # Allocate engine & create all tables/indexes/etc.
    test_engine = sqlalchemy.create_engine(TEST_SQLALCHEMY_DATABASE_URL)
    metadata.create_all(test_engine, tables=[users, agents, pairwises])
    test_database = databases.Database(TEST_SQLALCHEMY_DATABASE_URL)
    return test_database


async def override_get_db():
    """Override original database with test one in App routers dependency injections
    """
    test_database = databases.Database(TEST_SQLALCHEMY_DATABASE_URL)
    await test_database.connect()
    try:
        yield test_database
    finally:
        await test_database.disconnect()
