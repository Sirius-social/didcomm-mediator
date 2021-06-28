import databases
import sqlalchemy
from app.settings import SQLALCHEMY_DATABASE_URL


database = databases.Database(SQLALCHEMY_DATABASE_URL)
engine = sqlalchemy.create_engine(SQLALCHEMY_DATABASE_URL)
metadata = sqlalchemy.MetaData()
