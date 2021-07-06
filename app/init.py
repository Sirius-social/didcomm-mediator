import sirius_sdk
from databases import Database

from app.core.did import MediatorDID
from app.core.crypto import MediatorCrypto
from app.core.pairwise import MediatorPairwiseList
from app.settings import KEYPAIR, SQLALCHEMY_DATABASE_URL


db = Database(SQLALCHEMY_DATABASE_URL)  # Independent db connection


sirius_sdk.init(
    crypto=MediatorCrypto(*KEYPAIR),
    did=MediatorDID(db=db),
    pairwise_storage=MediatorPairwiseList(db=db)
)
