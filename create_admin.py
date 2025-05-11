from app import app, db, User
import logging
import sys
import os
from sqlalchemy import text

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def check_database_connection():
    try:
        # 测试数据库连接
        db.session.execute(text('SELECT 1'))
        logger.info("数据库连接成功")
        return True
    except Exception as e:
        logger.error(f"数据库连接失败: {str(e)}")
        return False

def create_admin():
    try:
        with app.app_context():
            # 检查数据库连接
            if not check_database_connection():
                return
            
            # 确保数据库表存在
            logger.info("正在检查数据库表...")
            db.create_all()
            
            # 检查是否已存在管理员
            logger.info("正在检查现有管理员...")
            admin = User.query.filter_by(role='admin').first()
            if admin:
                logger.info(f"管理员已存在: {admin.username}")
                return
            
            # 创建管理员账户
            logger.info("正在创建管理员账户...")
            admin = User(username='admin', role='admin')
            admin.set_password('admin123')  # 设置默认密码
            db.session.add(admin)
            
            try:
                db.session.commit()
                # 验证管理员是否创建成功
                admin = User.query.filter_by(username='admin').first()
                if admin and admin.role == 'admin':
                    logger.info("管理员账户创建成功！")
                    logger.info("用户名: admin")
                    logger.info("密码: admin123")
                    logger.info("请登录后立即修改密码！")
                else:
                    logger.error("管理员账户创建失败：无法验证账户")
            except Exception as e:
                db.session.rollback()
                logger.error(f"创建管理员账户失败: {str(e)}")
                raise
    except Exception as e:
        logger.error(f"发生错误: {str(e)}")
        raise

if __name__ == '__main__':
    try:
        # 打印环境变量（不包含敏感信息）
        logger.info(f"FLASK_APP: {os.getenv('FLASK_APP')}")
        logger.info(f"FLASK_ENV: {os.getenv('FLASK_ENV')}")
        logger.info(f"DATABASE_URL exists: {'DATABASE_URL' in os.environ}")
        
        create_admin()
    except Exception as e:
        logger.error(f"程序执行失败: {str(e)}")
        sys.exit(1) 