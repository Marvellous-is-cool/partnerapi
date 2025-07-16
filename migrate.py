from database import admins_collection

def remove_admin_type_field():
    """
    Migration to remove the 'type' field from all admin documents.
    """
    result = admins_collection.update_many(
        {"type": {"$exists": True}},
        {"$unset": {"type": ""}}
    )
    print(f"Removed 'type' field from {result.modified_count} admin(s).")

if __name__ == "__main__":
    remove_admin_type_field()