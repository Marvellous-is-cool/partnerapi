from typing import Dict
from bson import ObjectId
# from gridfs import GridFS
import gridfs
from pymongo import MongoClient
from datetime import datetime

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
admins_collection = db["admins"]
delivery_collection = db['deliveries']
chat_collection = db['chats']


fs = gridfs.GridFS(db)


# ================= Riders Functions =================

def insert_rider(rider_data, nationalid_file, facial_picture, utility_bill, bike_papers, riders_license_file):
    """
    Insert rider data into the database and store file uploads in GridFS.
    """
    # Save files to GridFS first
    nationalid_id = fs.put(nationalid_file, filename="nationalid", content_type="image/jpeg")
    facial_picture_id = fs.put(facial_picture, filename="facial_picture", content_type="image/jpeg")
    utility_bill_id = None
    if utility_bill:
        utility_bill_id = fs.put(utility_bill, filename="utility_bill", content_type="image/jpeg")
    bike_papers_id = fs.put(bike_papers, filename="bike_registration_papers", content_type="image/jpeg")
    riders_license_id = fs.put(riders_license_file, filename="riders_license", content_type="image/jpeg")

    # Add file_ids to rider_data
    rider_data["file_ids"] = {
        "nationalid": str(nationalid_id),
        "facial_picture": str(facial_picture_id),
        "utility_bill": str(utility_bill_id) if utility_bill_id else None,
        "bike_papers": str(bike_papers_id),
        "riders_license": str(riders_license_id),
    }

    # Set the facial_picture_url directly
    rider_data["facial_picture_url"] = f"https://deliveryapi-ten.vercel.app/files/{str(facial_picture_id)}"

    # Insert rider details with file_ids included
    rider_id = riders_collection.insert_one(rider_data).inserted_id

    return str(rider_id), rider_data["file_ids"]


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


def delete_rider_by_id(rider_id: str) -> bool:
    """
    Delete a rider by ID.
    """
    try:
        result = riders_collection.delete_one({"_id": ObjectId(rider_id)})
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error deleting rider: {e}")
        return False


def delete_selected_riders(rider_ids: list) -> int:
    """
    Delete multiple riders by their IDs.
    """
    try:
        object_ids = [ObjectId(rider_id) for rider_id in rider_ids]
        result = riders_collection.delete_many({"_id": {"$in": object_ids}})
        return result.deleted_count
    except Exception as e:
        print(f"Error deleting riders: {e}")
        return 0    
    
    
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


def delete_user_by_id(user_id: str) -> bool:
    """
    Delete a user by ID.
    """
    try:
        result = users_collection.delete_one({"_id": ObjectId(user_id)})
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error deleting user: {e}")
        return False


def delete_selected_users(user_ids: list) -> int:
    """
    Delete multiple users by their IDs.
    """
    try:
        object_ids = [ObjectId(user_id) for user_id in user_ids]
        result = users_collection.delete_many({"_id": {"$in": object_ids}})
        return result.deleted_count
    except Exception as e:
        print(f"Error deleting users: {e}")
        return 0    
    
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
    
    # Convert ObjectId to string for each delivery
    for delivery in deliveries:
        delivery["_id"] = str(delivery["_id"])
        
        # Ensure timestamp is in ISO format if it exists
        if "status" in delivery and isinstance(delivery["status"], dict) and "timestamp" in delivery["status"]:
            if isinstance(delivery["status"]["timestamp"], datetime):
                delivery["status"]["timestamp"] = delivery["status"]["timestamp"].isoformat()
                
        # Also convert last_updated if it exists
        if "last_updated" in delivery and isinstance(delivery["last_updated"], datetime):
            delivery["last_updated"] = delivery["last_updated"].isoformat()
            
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

def update_delivery(delivery_id, update_data):
    """
    Update delivery document in the database.
    """
    try:
        from bson import ObjectId
        
        # Convert string ID to ObjectId
        delivery_id_obj = ObjectId(delivery_id)
        
        # Handle the status update properly
        if "status" in update_data:
            # Check if rider_id is in update_data
            if "rider_id" in update_data:
                result = delivery_collection.update_one(
                    {"_id": delivery_id_obj},
                    {
                        "$set": {
                            "rider_id": update_data["rider_id"],
                            "status": update_data["status"],
                            "last_updated": datetime.utcnow()
                        }
                    }
                )
            else:
                # Just update the status without changing rider_id
                result = delivery_collection.update_one(
                    {"_id": delivery_id_obj},
                    {
                        "$set": {
                            "status": update_data["status"],
                            "last_updated": datetime.utcnow()
                        }
                    }
                )
        else:
            # For other updates (like rejected_riders)
            result = delivery_collection.update_one(
                {"_id": delivery_id_obj},
                {"$set": update_data}
            )
        
        print(f"Update result: {result.modified_count}")  # Debug print
        return result.modified_count > 0
        
    except Exception as e:
        print(f"Error in update_delivery: {str(e)}")  # Debug print
        return False


def get_file_by_id(file_id):
    """
    Retrieve a file from GridFS by its ID.
    """
    try:
        # Convert string ID to ObjectId
        file_id_obj = ObjectId(file_id)
        
        # Get all chunks for this file
        chunks = list(db.fs.chunks.find({'files_id': file_id_obj}).sort('n', 1))
        if not chunks:
            return None
            
        # Concatenate all binary chunks
        binary_data = b''.join(chunk['data'] for chunk in chunks)
        return binary_data
        
    except Exception as e:
        print(f"Error retrieving file: {e}")
        return None

def save_file_to_gridfs(file_data, filename, content_type="image/jpeg"):
    """
    Save a file to GridFS and return the file ID.
    """
    try:
        file_id = fs.put(file_data, filename=filename, content_type=content_type)
        return str(file_id)
    except Exception as e:
        print(f"Error saving file to GridFS: {e}")
        return None

def create_chat(sender_id: str, receiver_id: str, message: str, delivery_id: str):
    """
    Create a new chat message.
    """
    chat_data = {
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "message": message,
        "delivery_id": delivery_id,
        "timestamp": datetime.utcnow(),
        "read": False
    }
    result = chat_collection.insert_one(chat_data)
    return str(result.inserted_id)

def get_chat_history(delivery_id: str):
    """
    Get chat history for a specific delivery.
    """
    chats = list(chat_collection.find({"delivery_id": delivery_id}).sort("timestamp", 1))
    for chat in chats:
        chat["_id"] = str(chat["_id"])
        chat["timestamp"] = chat["timestamp"].isoformat()
    return chats

def mark_messages_as_read(receiver_id: str, delivery_id: str):
    """
    Mark all messages as read for a specific receiver and delivery.
    """
    result = chat_collection.update_many(
        {
            "receiver_id": receiver_id,
            "delivery_id": delivery_id,
            "read": False
        },
        {"$set": {"read": True}}
    )
    return result.modified_count > 0


# Add these collections after your existing collections
rider_ratings_collection = db['rider_ratings']
user_ratings_collection = db['user_ratings']

def rate_rider(rating_data):
    """
    Save a rating for a rider.
    """
    try:
        # Check if this user has already rated this rider for this delivery
        existing_rating = rider_ratings_collection.find_one({
            "user_id": rating_data["user_id"],
            "rider_id": rating_data["rider_id"],
            "delivery_id": rating_data["delivery_id"]
        })
        
        if existing_rating:
            # Update existing rating
            result = rider_ratings_collection.update_one(
                {"_id": existing_rating["_id"]},
                {"$set": {
                    "rating": rating_data["rating"],
                    "comment": rating_data["comment"],
                    "timestamp": rating_data["timestamp"]
                }}
            )
            return str(existing_rating["_id"]) if result.modified_count > 0 else None
        else:
            # Insert new rating
            result = rider_ratings_collection.insert_one(rating_data)
            return str(result.inserted_id)
    except Exception as e:
        print(f"Error saving rider rating: {e}")
        return None

def rate_user(rating_data):
    """
    Save a rating for a user.
    """
    try:
        # Check if this rider has already rated this user for this delivery
        existing_rating = user_ratings_collection.find_one({
            "user_id": rating_data["user_id"],
            "rider_id": rating_data["rider_id"],
            "delivery_id": rating_data["delivery_id"]
        })
        
        if existing_rating:
            # Update existing rating
            result = user_ratings_collection.update_one(
                {"_id": existing_rating["_id"]},
                {"$set": {
                    "rating": rating_data["rating"],
                    "comment": rating_data["comment"],
                    "timestamp": rating_data["timestamp"]
                }}
            )
            return str(existing_rating["_id"]) if result.modified_count > 0 else None
        else:
            # Insert new rating
            result = user_ratings_collection.insert_one(rating_data)
            return str(result.inserted_id)
    except Exception as e:
        print(f"Error saving user rating: {e}")
        return None

def get_rider_ratings(rider_id):
    """
    Get all ratings for a specific rider.
    """
    try:
        ratings = list(rider_ratings_collection.find({"rider_id": rider_id}))
        
        # Process ratings for JSON serialization
        for rating in ratings:
            rating["_id"] = str(rating["_id"])
            if "timestamp" in rating and isinstance(rating["timestamp"], datetime):
                rating["timestamp"] = rating["timestamp"].isoformat()
        
        return ratings
    except Exception as e:
        print(f"Error getting rider ratings: {e}")
        return []

def get_user_ratings(user_id):
    """
    Get all ratings for a specific user.
    """
    try:
        ratings = list(user_ratings_collection.find({"user_id": user_id}))
        
        # Process ratings for JSON serialization
        for rating in ratings:
            rating["_id"] = str(rating["_id"])
            if "timestamp" in rating and isinstance(rating["timestamp"], datetime):
                rating["timestamp"] = rating["timestamp"].isoformat()
        
        return ratings
    except Exception as e:
        print(f"Error getting user ratings: {e}")
        return []


def delete_account(user_id: str, account_type: str) -> bool:
    """
    Delete a user or rider account from the database based on their ID and account type.
    Returns True if the deletion was successful, False otherwise.
    """
    try:
        if account_type == "user":
            result = users_collection.delete_one({"_id": ObjectId(user_id)})
        elif account_type == "rider":
            result = riders_collection.delete_one({"_id": ObjectId(user_id)})
        else:
            raise ValueError("Invalid account type. Must be 'user' or 'rider'.")

        return result.deleted_count > 0
    except Exception as e:
        print(f"Error deleting account: {e}")
        return False
    
    
# ================= Admins Functions =================

def insert_admin(admin_data: dict):
    """
    Insert admin data into MongoDB with hashed password.
    """
    # Hash the password before storing
    admin_id = admins_collection.insert_one(admin_data).inserted_id
    return str(admin_id)


def get_admin_by_email(email: str):
    """
    Get admin data by email.
    """
    return admins_collection.find_one({"email": email})


def get_admin_by_username(username: str):
    """
    Get admin data by username.
    """
    return admins_collection.find_one({"username": username})


def get_admin_by_id(admin_id: str):
    """
    Get admin data by ID.
    """
    return admins_collection.find_one({"_id": ObjectId(admin_id)})
