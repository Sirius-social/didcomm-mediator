import uuid

import pytest
import sirius_sdk

from .helpers import allocate_test_database


@pytest.fixture()
def random_username() -> str:
    rnd = uuid.uuid4().hex
    return f'user_{rnd}'


@pytest.fixture()
def random_password() -> str:
    rnd = uuid.uuid4().hex
    return f'password_{rnd}'


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
def random_keys() -> (str, str):
    """
    Generate Random verkey+secret

    :return: verkey, privkey
    """
    pub_key, priv_key = sirius_sdk.encryption.ed25519.create_keypair()
    return sirius_sdk.encryption.bytes_to_b58(pub_key), sirius_sdk.encryption.bytes_to_b58(priv_key)


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
def random_fcm_device_id() -> str:
    return uuid.uuid4().hex


@pytest.fixture()
def random_redis_pub_sub() -> str:
    return f'redis://redis1/{uuid.uuid4().hex}'


@pytest.fixture()
def random_endpoint_uid() -> str:
    return uuid.uuid4().hex


@pytest.fixture()
async def test_database():
    test_database = await allocate_test_database()
    await test_database.connect()
    try:
        yield test_database
    finally:
        await test_database.disconnect()


@pytest.fixture()
def didcomm_envelope_enc_content() -> bytes:
    return b'{"protected": "eyJlbmMiOiAieGNoYWNoYTIwcG9seTEzMDVfaWV0ZiIsICJ0eXAiOiAiSldNLzEuMCIsICJhbGciOiAiQXV0aGNyeXB0IiwgInJlY2lwaWVudHMiOiBbeyJlbmNyeXB0ZWRfa2V5IjogInBKcW1xQS1IVWR6WTNWcFFTb2dySGx4WTgyRnc3Tl84YTFCSmtHU2VMT014VUlwT0RQWTZsMVVsaVVvOXFwS0giLCAiaGVhZGVyIjogeyJraWQiOiAiM1ZxZ2ZUcDZRNFZlRjhLWTdlVHVXRFZBWmFmRDJrVmNpb0R2NzZLR0xtZ0QiLCAic2VuZGVyIjogIjRlYzhBeFRHcWtxamd5NHlVdDF2a0poeWlYZlNUUHo1bTRKQjk1cGZSMG1JVW9KajAwWmswNmUyUEVDdUxJYmRDck8xeTM5LUhGTG5NdW5YQVJZWk5rZ2pyYV8wYTBQODJpbVdNcWNHc1FqaFd0QUhOcUw1OGNkUUYwYz0iLCAiaXYiOiAiVU1PM2o1ZHZwQnFMb2Rvd3V0c244WEMzTkVqSWJLb2oifX1dfQ==", "iv": "MchkHF2M-4hneeUJ", "ciphertext": "UgcdsV-0rIkP25eJuRSROOuqiTEXp4NToKjPMmqqtJs-Ih1b5t3EEbrrHxeSfPsHtlO6J4OqA1jc5uuD3aNssUyLug==", "tag": "sQD8qgJoTrRoyQKPeCSBlQ=="}'
