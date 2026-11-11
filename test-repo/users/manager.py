"""
User management module for CRUD operations on user accounts.
Provides functions to create, read, update, and delete users.
"""

from flask import Blueprint, request, jsonify
from database.connection import get_database_connection
from auth.login import hash_password

users_blueprint = Blueprint('users', __name__)

class UserManager:
    """Manages user CRUD operations."""
    
    def __init__(self):
        """Initialize UserManager with database connection."""
        self.db = get_database_connection()
    
    def create_user(self, email: str, password: str, name: str) -> dict:
        """
        Create a new user account.
        
        Args:
            email: User's email address
            password: User's password (will be hashed)
            name: User's full name
            
        Returns:
            Created user dictionary
        """
        password_hash = hash_password(password)
        
        user = {
            "email": email,
            "password_hash": password_hash,
            "name": name,
            "is_active": True
        }
        
        # Insert into database
        user_id = self.db.insert_user(user)
        user['id'] = user_id
        
        return user
    
    def get_user(self, user_id: int) -> dict:
        """
        Get user by ID.
        
        Args:
            user_id: User's unique identifier
            
        Returns:
            User dictionary or None if not found
        """
        return self.db.get_user_by_id(user_id)
    
    def get_all_users(self) -> list:
        """
        Get all users in the system.
        
        Returns:
            List of user dictionaries
        """
        return self.db.get_all_users()
    
    def update_user(self, user_id: int, updates: dict) -> bool:
        """
        Update user information.
        
        Args:
            user_id: User's unique identifier
            updates: Dictionary of fields to update
            
        Returns:
            True if update successful, False otherwise
        """
        return self.db.update_user(user_id, updates)
    
    def delete_user(self, user_id: int) -> bool:
        """
        Delete a user account.
        
        Args:
            user_id: User's unique identifier
            
        Returns:
            True if deletion successful, False otherwise
        """
        return self.db.delete_user(user_id)
    
    def search_users(self, query: str) -> list:
        """
        Search users by name or email.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching users
        """
        return self.db.search_users(query)

@users_blueprint.route('/', methods=['GET'])
def list_users():
    """Get all users endpoint."""
    manager = UserManager()
    users = manager.get_all_users()
    return jsonify({"users": users}), 200

@users_blueprint.route('/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get single user by ID endpoint."""
    manager = UserManager()
    user = manager.get_user(user_id)
    
    if user:
        return jsonify(user), 200
    else:
        return jsonify({"error": "User not found"}), 404

@users_blueprint.route('/', methods=['POST'])
def create_user():
    """Create new user endpoint."""
    data = request.get_json()
    manager = UserManager()
    
    try:
        user = manager.create_user(
            email=data['email'],
            password=data['password'],
            name=data['name']
        )
        return jsonify({"message": "User created", "user": user}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@users_blueprint.route('/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Update user endpoint."""
    data = request.get_json()
    manager = UserManager()
    
    if manager.update_user(user_id, data):
        return jsonify({"message": "User updated"}), 200
    else:
        return jsonify({"error": "Update failed"}), 400
