from flask_pymongo import PyMongo
from config import MONGO_URI
from flask import Flask

mongo = PyMongo()

# Global collections
users_collection = None
chat_history_collection = None
feedback_collection = None
question_collection = None

def init_db(app: Flask):  # Explicit type hinting
    """Initialize the database connection"""
    app.config["MONGO_URI"] = MONGO_URI
    mongo.init_app(app)
    print("✅ MongoDB connected successfully!")
    return initialize_collections()  # Return the result of initialize_collections

def get_database():
    """Return the AIRA database instance"""
    if mongo.db is None:
        print("⚠️ mongo.db is None. Database not initialized yet.")
        raise RuntimeError("MongoDB is not initialized. Call init_db(app) first.")

    print("🟢 MongoDB instance fetched successfully!")
    return mongo.db  # 🔹 Fetch the DB dynamically to avoid None issues

def initialize_collections():
    """Ensure database is initialized after setting collections"""
    global users_collection, chat_history_collection, feedback_collection, question_collection

    try:
        db = mongo.db  # Direct access to avoid potential recursive call

        if db is None:
            print("❌ Database instance is None. Initialization failed!")
            return False

        print(f"✅ Database instance fetched: {db}")

        users_collection = db["users"]
        chat_history_collection = db["chat_history"]
        feedback_collection = db["feedback"]
        question_collection = db["questions"]

        # 🔍 Debugging print statements
        print(f"✅ Collections initialized successfully!")
        print(f"🔍 question_collection: {question_collection}")  # Debugging print
        
        # Verify collections are properly set
        if question_collection is None:
            print("❌ question_collection is still None after initialization!")
            return False
            
        return True

    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False