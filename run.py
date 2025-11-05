"""
ResearchHub Pro - AI-Powered Research Intelligence Platform
Main application entry point
"""
import os
from app import create_app

# Create Flask application
app = create_app(os.getenv('FLASK_ENV', 'development'))

if __name__ == '__main__':
    # Run the application
    app.run(
        host=os.getenv('HOST', '0.0.0.0'),
        port=int(os.getenv('PORT', 5000)),
        debug=app.config['DEBUG']
    )
