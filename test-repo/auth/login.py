"""
Authentication module for user login and password verification.
Uses bcrypt for secure password hashing.
"""

import bcrypt
from flask import Blueprint, request, jsonify
from database.connection import get_user_by_email

login_blueprint = Blueprint('login', __name__)

def hash_password(password: str) -> bytes:
    """
    Hash a password using bcrypt with a salt.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password bytes
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt)

def verify_password(password: str, hashed: bytes) -> bool:
    """
    Verify a password against a hash.
    
    Args:
        password: Plain text password to verify
        hashed: Hashed password to compare against
        
    Returns:
        True if password matches, False otherwise
    """
    return bcrypt.checkpw(password.encode('utf-8'), hashed)

def authenticate_user(email: str, password: str):
    """
    Authenticate a user with email and password.
    
    Args:
        email: User's email address
        password: User's password
        
    Returns:
        User object if authentication successful, None otherwise
    """
    user = get_user_by_email(email)
    
    if not user:
        return None
    
    if verify_password(password, user['password_hash']):
        return user
    
    return None

@login_blueprint.route('/login', methods=['POST'])
def login():
    """
    Login endpoint for user authentication.
    
    Request JSON:
        {
            "email": "user@example.com",
            "password": "password123"
        }
    
    Returns:
        JSON response with user data or error message
    """
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    
    user = authenticate_user(email, password)
    
    if user:
        return jsonify({
            "message": "Login successful",
            "user": {
                "id": user['id'],
                "email": user['email'],
                "name": user['name']
            }
        }), 200
    else:
        return jsonify({"error": "Invalid credentials"}), 401

@login_blueprint.route('/logout', methods=['POST'])
def logout():
    """Logout endpoint to clear user session."""
    return jsonify({"message": "Logout successful"}), 200
