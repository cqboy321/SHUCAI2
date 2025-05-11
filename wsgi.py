import os
import sys
import logging
from app import app, db, User

# 配置日志
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    try:
        with app.app_context():
            # 创建数据库表
            db.create_all()
            logger.info("Database tables created successfully")
            
            # 检查并创建管理员账户
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

# 在应用启动时初始化数据库
init_db()

if __name__ == "__main__":
    app.run() 