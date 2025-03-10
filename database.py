from typing import Dict
from bson import ObjectId
import gridfs
from pymongo import MongoClient
from hashlib import sha256

# MongoDB connection details
MONGO_URI = (
    "mongodb+srv://primidac:teststring123###@micodelivery.mqfic.mongodb.net/"
    "?retryWrites=true&w=majority&appName=micodelivery"
)  # Update with your MongoDB URI
DATABASE_NAME = "delivery_app_db"

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]
riders_collection = db["riders"]
users_collection = db["users"]
delivery_collection = db['deliveries']

fs = gridfs.GridFS(db)


# ================= Riders Functions =================

def insert_rider(rider_data, nationalid_file, facial_picture, utility_bill, bike_papers, riders_license_file):
    """
    Insert rider data into the database and store file uploads in GridFS.
    """
    # Insert rider details
    rider_id = riders_collection.insert_one(rider_data).inserted_id

    # Save files to GridFS
    nationalid_id = fs.put(nationalid_file, filename="nationalid")
    facial_picture_id = fs.put(facial_picture, filename="facial_picture")
    utility_bill_id = fs.put(utility_bill, filename="utility_bill")
    bike_papers_id = fs.put(bike_papers, filename="bike_registration_papers")
    riders_license_id = fs.put(riders_license_file, filename="riders_license")

    return str(rider_id), {
        "nationalid": str(nationalid_id),
        "facial_picture": str(facial_picture_id),
        "utility_bill": str(utility_bill_id),
        "bike_papers": str(bike_papers_id),
        "riders_license": str(riders_license_id),
    }


def get_rider_by_email(email: str):
    """
    Get rider data by email.
    """
    return riders_collection.find_one({"email": email})


def get_rider_by_id(rider_id: str):
    """
    Get rider data by ID.
    """
    return riders_collection.find_one({"_id": ObjectId(rider_id)})


def get_all_riders():
    """
    Fetch all riders' data.
    """
    riders = list(riders_collection.find())
    for rider in riders:
        rider["_id"] = str(rider["_id"])
    return riders


# ================= Users Functions =================

def insert_user(user_data: dict):
    """
    Insert user data into MongoDB with hashed password.
    """
    # Hash the password before storing
    user_id = users_collection.insert_one(user_data).inserted_id
    return str(user_id)


def get_user_by_email(email: str):
    """
    Get user data by email.
    """
    return users_collection.find_one({"email": email})


def get_user_by_id(user_id: str):
    """
    Get user data by ID.
    """
    return users_collection.find_one({"_id": ObjectId(user_id)})


def get_all_users():
    """
    Fetch all users' data.
    """
    users = list(users_collection.find())
    for user in users:
        user["_id"] = str(user["_id"])
    return users


# ================= Utility Functions =================

def ping_database():
    """
    Ping the database to check connection.
    """
    try:
        client.admin.command("ping")
        return True
    except Exception as e:
        print(f"Error pinging database: {e}")
        return False
    
def insert_delivery(delivery_data: Dict) -> str:
    """
    Function to insert delivery data into MongoDB and return the delivery ID.
    """
    # Insert the delivery data into the MongoDB collection
    result = delivery_collection.insert_one(delivery_data)
    return str(result.inserted_id)

def get_all_deliveries():
    """
    Fetch all deliveries from the database.
    """
    deliveries = list(delivery_collection.find())  # Get all deliveries
    for delivery in deliveries:
        delivery["_id"] = str(delivery["_id"])  # Convert ObjectId to string
    return deliveries

def get_delivery_by_id(delivery_id: str):
    """
    Fetch a delivery by its ID from the database.
    """
    delivery = delivery_collection.find_one({"_id": ObjectId(delivery_id)})

    if delivery:
        delivery["_id"] = str(delivery["_id"])  # Convert ObjectId to string
    return delivery


def update_rider_status(rider_id: str, new_status: str) -> bool:
    """
    Update rider's status in the database.
    Returns True if update was successful, False otherwise.
    """
    try:
        result = riders_collection.update_one(
            {"_id": ObjectId(rider_id)},
            {"$set": {"status": new_status}}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating rider status: {e}")
        return False


def update_rider_details_db(rider_id: str, update_data: dict) -> bool:
    """
    Update rider's details in the database.
    Returns True if update was successful, False otherwise.
    """
    try:
        result = riders_collection.update_one(
            {"_id": ObjectId(rider_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating rider details: {e}")
        return False

def update_user_details_db(user_id: str, update_data: dict) -> bool:
    """
    Update user's details in the database.
    Returns True if update was successful, False otherwise.
    """
    try:
        result = users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating user details: {e}")
        return False