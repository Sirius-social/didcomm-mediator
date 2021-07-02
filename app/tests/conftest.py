import pytest
import sirius_sdk

from .helpers import allocate_test_database


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
def random_their() -> (str, str, str):
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
    test_database = await allocate_test_database()
    await test_database.connect()
    try:
        yield test_database
    finally:
        await test_database.disconnect()
