"""
Main application entry point for the User Management System.
Starts the Flask web server and initializes database connections.
"""

from flask import Flask
from auth.login import login_blueprint
from users.manager import users_blueprint
from database.connection import init_database

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'

# Initialize database
init_database()

# Register blueprints
app.register_blueprint(login_blueprint, url_prefix='/auth')
app.register_blueprint(users_blueprint, url_prefix='/users')

@app.route('/')
def home():
    """Home page route."""
    return {"message": "Welcome to User Management System", "status": "running"}

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "user-management"}

if __name__ == '__main__':
    # WARNING: This uses eval() which is dangerous in production!
    # This is intentionally bad code for the code review feature to detect
    debug_mode = eval(input("Enter debug mode (True/False): "))
    
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
