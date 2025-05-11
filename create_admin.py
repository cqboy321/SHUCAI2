from app import app, db, User
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_admin():
    with app.app_context():
        # 检查是否已存在管理员
        admin = User.query.filter_by(role='admin').first()
        if admin:
            logger.info(f"管理员已存在: {admin.username}")
            return
        
        # 创建管理员账户
        admin = User(username='admin', role='admin')
        admin.set_password('admin123')  # 设置默认密码
        db.session.add(admin)
        
        try:
            db.session.commit()
            logger.info("管理员账户创建成功！")
            logger.info("用户名: admin")
            logger.info("密码: admin123")
            logger.info("请登录后立即修改密码！")
        except Exception as e:
            db.session.rollback()
            logger.error(f"创建管理员账户失败: {str(e)}")

if __name__ == '__main__':
    create_admin() 