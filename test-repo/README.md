# User Management System

A simple Python-based user management system with authentication and profile management.

## Features

- User registration and login
- Password hashing with bcrypt
- Session management
- User profile CRUD operations
- Admin dashboard

## Installation

```bash
pip install -r requirements.txt
python main.py
```

## Usage

```python
from auth.login import authenticate_user
from users.manager import UserManager

# Authenticate user
user = authenticate_user("john@example.com", "password123")

# Manage users
manager = UserManager()
users = manager.get_all_users()
```
