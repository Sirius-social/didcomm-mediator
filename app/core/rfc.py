def extract_key(value: str) -> str:
    """Implement https://github.com/hyperledger/aries-rfcs/blob/master/features/0360-use-did-key/README.md
    """
    # "did:key:z6MkmjY8GnV5i9YTDtPETC2uUAW6ejw3nk5mXF5yci5ab7th"
    return value.split(':')[-1]
