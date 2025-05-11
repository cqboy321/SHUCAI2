#!/usr/bin/env python
"""
Fix deployment issues for the Flask application on the server.
This script ensures the correct imports are in wsgi.py and handles database setup.
"""
import os
import codecs
import sys
import re

# File paths
wsgi_path = "wsgi.py"
config_path = "config.py"

# 确保config.py正确处理PostgreSQL URL
def fix_config_file():
    if not os.path.exists(config_path):
        print(f"Warning: {config_path} not found!")
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # 检查是否已经有PostgreSQL URL修复
        has_postgres_fix = 'postgres://' in content and 'postgresql://' in content
        
        if has_postgres_fix:
            print(f"The file {config_path} already has the PostgreSQL URL fix.")
            return True
        
        # 添加PostgreSQL URL处理代码
        new_content = re.sub(
            r'SQLALCHEMY_DATABASE_URI\s*=\s*os\.environ\.get\(\'DATABASE_URL\'\)\s*or\s*\'sqlite:///inventory\.db\'',
            """# 处理Render PostgreSQL连接字符串
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith('postgres://'):
        # 修正Heroku/Render兼容性问题 - 从postgres://变为postgresql://
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = database_url or 'sqlite:///inventory.db'""",
            content
        )
        
        if new_content != content:
            # 备份原始文件
            backup_path = f"{config_path}.bak"
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Created backup of original config file at {backup_path}")
            
            # 写入新内容
            with codecs.open(config_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Fixed {config_path} with PostgreSQL URL handling")
            return True
        else:
            print(f"Could not update {config_path}, regex match failed")
            return False
    except Exception as e:
        print(f"Error fixing config file: {str(e)}")
        return False

# New content to ensure request is properly imported and fix Content-Encoding issues
correct_wsgi_content = """import os
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
            # Check the database type
            db_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
            is_postgres = 'postgresql' in db_url
            
            if is_postgres:
                logger.info("Using PostgreSQL database: %s", db_url.split('@')[1] if '@' in db_url else db_url)
                
                # 尝试先连接数据库
                try:
                    db.session.execute('SELECT 1')
                    logger.info("Database connection successful")
                except Exception as e:
                    logger.warning("Initial database connection failed: %s", str(e))
                    logger.info("Will create tables next...")
            else:
                logger.info("Using SQLite database")
            
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
                
            # Create default product prices if needed
            from app import ProductPrice
            if ProductPrice.query.count() == 0:
                logger.info("Setting up default product prices...")
                from datetime import datetime
                try:
                    # 尝试为每个蔬菜创建默认价格记录
                    vegetables = ['空心菜', '水白菜', '水萝卜', '油麦菜', '菜心', '塔菜', '白萝卜', '快白菜', '小白菜', '大白菜']
                    for vegetable in vegetables:
                        price = ProductPrice(
                            name=vegetable,
                            sale_price=10.0,  # 默认销售价格
                            start_date=datetime.now()
                        )
                        db.session.add(price)
                    db.session.commit()
                    logger.info("Default product prices created successfully")
                except Exception as e:
                    logger.error("Failed to create default product prices: %s", str(e))
                    db.session.rollback()
                
    except Exception as e:
        logger.error(f"Error during database initialization: {str(e)}")
        raise

# Initialize the database when the application starts
init_db()

# Configure the application
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 year
app.config['TEMPLATES_AUTO_RELOAD'] = False  # Disable template auto-reload

if __name__ == "__main__":
    app.run()"""

def main():
    # 首先修复配置文件
    fix_config_file()
    
    # Check if wsgi.py exists
    if not os.path.exists(wsgi_path):
        print(f"Error: {wsgi_path} not found!")
        sys.exit(1)

    try:
        # Open the file to check if it has the correct import and encoding fix
        with open(wsgi_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        # Check if the file already has both fixes
        has_request_import = 'from flask import request' in content
        has_encoding_fix = 'del response.headers[\'Content-Encoding\']' in content
        has_postgres_check = 'is_postgres = ' in content
        
        if has_request_import and has_encoding_fix and has_postgres_check:
            print(f"The file {wsgi_path} already has all the necessary fixes.")
        else:
            # Back up the original file
            backup_path = f"{wsgi_path}.bak"
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Created backup of original file at {backup_path}")
            
            # Write the correct content
            with codecs.open(wsgi_path, 'w', encoding='utf-8') as f:
                f.write(correct_wsgi_content)
            print(f"Fixed {wsgi_path} with correct imports, Content-Encoding fix, and PostgreSQL handling")
            
        # 创建或确保favicon.ico存在
        favicon_dir = os.path.join("static")
        favicon_path = os.path.join(favicon_dir, "favicon.ico")
        
        if not os.path.exists(favicon_path) and os.path.exists("vegetable.ico"):
            if not os.path.exists(favicon_dir):
                os.makedirs(favicon_dir)
            # 复制vegetable.ico作为favicon.ico
            with open("vegetable.ico", "rb") as src, open(favicon_path, "wb") as dst:
                dst.write(src.read())
            print(f"Created favicon.ico from vegetable.ico")
        
        print("Deployment fix completed successfully!")
    except Exception as e:
        print(f"Error fixing deployment: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 