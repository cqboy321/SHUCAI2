import os
import sys
import logging
from flask import request
from app import app, db, User
from werkzeug.middleware.proxy_fix import ProxyFix
import eventlet

# Patch eventlet for better performance
eventlet.monkey_patch()

# 配置日志
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

# 添加性能优化中间件
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_for=1)

# 缓存控制和安全头
@app.after_request
def add_header(response):
    # 静态资源长缓存
    if request.path.startswith('/static'):
        response.cache_control.max_age = 31536000
        response.cache_control.public = True
    else:
        response.cache_control.no_store = True
        response.cache_control.no_cache = True
        response.cache_control.must_revalidate = True
        response.headers['Pragma'] = 'no-cache'

    # 安全头
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'

    # 不要手动加 gzip header！
    return response

def init_db():
    try:
        with app.app_context():
            db.create_all()
            logger.info("Database tables created successfully")
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

# 初始化数据库
init_db()

# 配置应用
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1年
app.config['TEMPLATES_AUTO_RELOAD'] = False  # 禁用模板自动重载

if __name__ == "__main__":
    app.run()
