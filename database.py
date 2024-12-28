from bson import ObjectId
import gridfs
from pymongo import MongoClient

# MongoDB connection details
MONGO_URI = "mongodb+srv://primidac:teststring123###@micodelivery.mqfic.mongodb.net/?retryWrites=true&w=majority&appName=micodelivery"  # Update with your MongoDB URI
DATABASE_NAME = "delivery_app_db"
# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]
riders_collection = db["riders"]

fs = gridfs.GridFS(db)

# Function to insert rider data and national ID into MongoDB
def insert_rider(rider_data: dict, nationalid_file: bytes):
    rider_id = riders_collection.insert_one(rider_data).inserted_id
    nationalid_file_id = fs.put(nationalid_file, filename="nationalid.jpg")
    return str(rider_id), str(nationalid_file_id)

# Function to ping the database to check connection
def ping_database():
    try:
        client.admin.command('ping')
        return True
    except Exception as e:
        print(f"Error pinging database: {e}")
        return False

# Function to get rider data by email
def get_rider_by_email(email: str):
    rider = riders_collection.find_one({"email": email})
    return rider

# Function to get rider data by ID
def get_rider_by_id(rider_id: str):
    rider = riders_collection.find_one({"_id": ObjectId(rider_id)})
    return rider

# Function to fetch all riders' data
def get_all_riders():
    riders = list(riders_collection.find())
    for rider in riders:
        rider["_id"] = str(rider["_id"])  # Convert ObjectId to string
    return riders