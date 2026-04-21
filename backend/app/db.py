from pymongo import AsyncMongoClient

from app.config import settings

mongo_client: AsyncMongoClient | None = None


async def connect(document_models: list[type]) -> None:
    global mongo_client
    from beanie import init_beanie

    mongo_client = AsyncMongoClient(settings.database_uri)
    database = mongo_client.get_default_database()
    if database is None:
        raise ValueError(
            "database_uri must include a database name in the path, "
            "e.g. mongodb://localhost:27017/mwallet"
        )
    await init_beanie(
        database=database,
        document_models=document_models,
    )


async def disconnect() -> None:
    global mongo_client
    if mongo_client is not None:
        await mongo_client.close()
        mongo_client = None


def get_mongo_client() -> AsyncMongoClient:
    if mongo_client is None:
        raise RuntimeError("MongoDB client is not initialized")
    return mongo_client
