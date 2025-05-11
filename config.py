import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    
    # 处理Render PostgreSQL连接字符串
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith('postgres://'):
        # 修正Heroku/Render兼容性问题 - 从postgres://变为postgresql://
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = database_url or 'sqlite:///inventory.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False 