from flask_pymongo import PyMongo
from config import MONGO_URI

mongo = PyMongo()

# Global collections
users_collection = None
chat_history_collection = None
feedback_collection = None

def init_db(app):
    """Initialize the database connection"""
    app.config["MONGO_URI"] = MONGO_URI
    mongo.init_app(app)
    print("✅ MongoDB connected successfully!")

def get_database():
    """Return the AIRA database instance"""
    if mongo.db is None:
        print("⚠️ mongo.db is None. Database not initialized yet.")
        raise RuntimeError("MongoDB is not initialized. Call init_db(app) first.")
    
    print("🟢 MongoDB instance fetched successfully!")
    return mongo.db  # 🔹 Fetch the DB dynamically to avoid None issues

def initialize_collections():
    """Ensure database is initialized before setting collections"""
    global users_collection, chat_history_collection, feedback_collection, blacklisted_tokens_collection

    try:
        db = get_database()

        if db is None:
            print("❌ Database instance is None. Initialization failed!")
            return

        print(f"✅ Database instance fetched: {db}")

        users_collection = db["users"]
        chat_history_collection = db["chat_history"]
        feedback_collection = db["feedback"]

        # 🔍 Debugging print statements
        print(f"✅ Collections initialized successfully!")
        # print(f"🔍 blacklisted_tokens_collection: {blacklisted_tokens_collection}")

    except RuntimeError as e:
        print(f"❌ Database initialization failed: {e}")

