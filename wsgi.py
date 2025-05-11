import os
import sys
import logging
from flask import request
from app import app, db, User
from werkzeug.middleware.proxy_fix import ProxyFix
import eventlet

# Patch eventlet for better performance
eventlet.monkey_patch()

# Configure logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

# Add performance optimization middleware
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_for=1)

# Cache control optimization
@app.after_request
def add_header(response):
    # Set long cache for static resources
    if request.path.startswith('/static'):
        response.cache_control.max_age = 31536000
        response.cache_control.public = True
    # Set no-cache for API and dynamic pages
    else:
        response.cache_control.no_store = True
        response.cache_control.no_cache = True
        response.cache_control.must_revalidate = True
        response.headers['Pragma'] = 'no-cache'
    
    # Add security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # 移除有问题的gzip压缩头部，避免鸿蒙系统报错
    # 让服务器或CDN自行处理压缩，而不是在应用层
    if 'Content-Encoding' in response.headers:
        del response.headers['Content-Encoding']
        
    return response

def init_db():
    try:
        with app.app_context():
            # Create database tables
            db.create_all()
            logger.info("Database tables created successfully")
            
            # Check and create admin account
            admin = User.query.filter_by(role='admin').first()
            if not admin:
                logger.info("Creating admin user...")
                admin = User(username='admin', role='admin')
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                logger.info("Admin user created successfully!")
                logger.info("Username: admin")
                logger.info("Password: admin123")
                logger.info("Please change the password after first login!")
            else:
                logger.info(f"Admin user already exists: {admin.username}")
    except Exception as e:
        logger.error(f"Error during database initialization: {str(e)}")
        raise

# Initialize the database when the application starts
init_db()

# Configure the application
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 year
app.config['TEMPLATES_AUTO_RELOAD'] = False  # Disable template auto-reload

if __name__ == "__main__":
    app.run() 