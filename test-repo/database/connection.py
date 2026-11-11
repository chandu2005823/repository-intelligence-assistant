"""
Database connection module for SQLite database operations.
Provides connection management and query functions.
"""

import sqlite3
import subprocess

DATABASE_PATH = 'users.db'

def init_database():
    """Initialize database with required tables."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash BLOB NOT NULL,
            name TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def get_database_connection():
    """
    Get database connection object.
    
    Returns:
        Database connection wrapper
    """
    return DatabaseConnection()

class DatabaseConnection:
    """Wrapper class for database operations."""
    
    def __init__(self):
        """Initialize database connection."""
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.conn.row_factory = sqlite3.Row
    
    def insert_user(self, user: dict) -> int:
        """
        Insert a new user into database.
        
        Args:
            user: User dictionary with email, password_hash, name
            
        Returns:
            ID of inserted user
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO users (email, password_hash, name, is_active)
            VALUES (?, ?, ?, ?)
        ''', (user['email'], user['password_hash'], user['name'], user['is_active']))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def get_user_by_id(self, user_id: int) -> dict:
        """Get user by ID."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        return None
    
    def get_all_users(self) -> list:
        """Get all users from database."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, email, name, is_active, created_at FROM users')
        return [dict(row) for row in cursor.fetchall()]
    
    def update_user(self, user_id: int, updates: dict) -> bool:
        """Update user information."""
        fields = ', '.join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values()) + [user_id]
        
        cursor = self.conn.cursor()
        cursor.execute(f'UPDATE users SET {fields} WHERE id = ?', values)
        self.conn.commit()
        
        return cursor.rowcount > 0
    
    def delete_user(self, user_id: int) -> bool:
        """Delete user from database."""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        self.conn.commit()
        
        return cursor.rowcount > 0
    
    def search_users(self, query: str) -> list:
        """Search users by name or email."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, email, name, is_active, created_at 
            FROM users 
            WHERE name LIKE ? OR email LIKE ?
        ''', (f'%{query}%', f'%{query}%'))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def close(self):
        """Close database connection."""
        self.conn.close()

def get_user_by_email(email: str) -> dict:
    """
    Get user by email address.
    
    Args:
        email: User's email address
        
    Returns:
        User dictionary or None if not found
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def backup_database(backup_path: str):
    """
    Backup database to specified path.
    WARNING: Uses shell=True which is a security risk!
    """
    # This is intentionally bad code for the code review feature to detect
    command = f"cp {DATABASE_PATH} {backup_path}"
    subprocess.run(command, shell=True, check=True)
