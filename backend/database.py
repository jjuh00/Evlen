from motor.motor_asyncio import AsyncIOMotorClient

from config import settings

# Module-level reference to the database client
client: AsyncIOMotorClient | None = None
db = None

async def connect_database() -> None:
    """
    Open a connection to MongoDB using Motor. The connection URL and database name are read from the settings.
    Called during app startup to initialize the database connection. Pings the database to verify connectivity.

    Raises:
        Exception: Motor/pymongo errors if connection fails, which will prevent the app from starting.
    """
    global client, db

    client = AsyncIOMotorClient(settings.mongo_url)
    db = client[settings.mongo_db]

    # Ping verifies the connection is actually established and the database is reachable
    await client.admin.command("ping")
    print(f"[DB] Connected to MongoDB with database: {settings.mongo_db}")

async def close_database() -> None:
    """
    Cleanly close the Motor client connection to MongoDB. 
    Called during app shutdown to release resources.
    """
    global client
    if client:
        client.close()
        print("[DB] MongoDB connection closed")

def get_database() -> AsyncIOMotorClient:
    """
    FastAPI dependency function to provide access to the MongoDB database instance.
    Inject into route function that need database access.

    Returns:
        AsyncIOMotorClient: The Motor client instance.
    
    Raises:
        RuntimeError: If called before the database connection is established (client is None).
    """
    if db is None:
        raise RuntimeError("Database is not initialized. Ensure connect_database() is called during app startup.")
    return db