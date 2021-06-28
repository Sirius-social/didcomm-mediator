from app.db.database import database


async def get_db():
    if not database.is_connected:
        await database.connect()
    return database
