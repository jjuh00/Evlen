from motor.motor_asyncio import AsyncIOMotorClient

from config import settings

# Module-level reference to the database client
client: AsyncIOMotorClient | None = None
db = None

async def connect_database():
    global client, db
    client = AsyncIOMotorClient(settings.mongo_url)
    db = client[settings.mongo_db]
    # Ping to verify connection
    await client.admin.command("ping")
    print(f"[Database] Connected to MongoDB: {settings.mongo_db}")

async def close_database():
    global client
    if client:
        client.close()
        print("[Database] MongoDB connection closed")