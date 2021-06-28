import pytest
import sirius_sdk


@pytest.fixture()
def random_keypair() -> (str, str):
    pub_key, priv_key = sirius_sdk.encryption.ed25519.create_keypair()
    return sirius_sdk.encryption.bytes_to_b58(pub_key), sirius_sdk.encryption.bytes_to_b58(priv_key)
