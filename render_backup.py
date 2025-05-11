import os
import time
import sqlite3
import logging
import requests
from datetime import datetime
import boto3
import pandas as pd
from io import BytesIO
import sqlalchemy
from sqlalchemy.orm import sessionmaker
from app import db, User, Product, ProductPrice, ActivityLog
from config import Config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def backup_to_s3():
    """备份数据库到AWS S3（如果配置了S3凭证）"""
    try:
        aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        s3_bucket = os.environ.get('S3_BACKUP_BUCKET')
        
        if not all([aws_access_key, aws_secret_key, s3_bucket]):
            logger.warning("AWS S3凭证未完全配置，跳过S3备份")
            return False
        
        # 创建S3客户端
        s3 = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )
        
        # 创建时间戳文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"db_backup_{timestamp}.sqlite"
        
        # 获取数据库路径
        db_path = os.environ.get('DATABASE_URL', 'sqlite:///inventory.db')
        if db_path.startswith('sqlite:///'):
            db_path = db_path[10:]  # 移除 'sqlite:///'
        
        # 复制数据库文件
        conn = sqlite3.connect(db_path)
        backup_conn = sqlite3.connect(backup_filename)
        conn.backup(backup_conn)
        backup_conn.close()
        conn.close()
        
        # 上传到S3
        s3.upload_file(backup_filename, s3_bucket, backup_filename)
        
        # 清理临时文件
        os.remove(backup_filename)
        
        logger.info(f"成功备份数据库到S3: {s3_bucket}/{backup_filename}")
        return True
    
    except Exception as e:
        logger.error(f"S3备份失败: {str(e)}")
        return False

def export_to_excel():
    """将数据导出为Excel文件"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 创建一个字节流来存储Excel文件
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # 导出产品数据
            products = Product.query.all()
            product_data = []
            for p in products:
                product_data.append({
                    'ID': p.id,
                    '商品名称': p.name,
                    '类型': p.type,
                    '价格': p.price,
                    '数量': p.quantity,
                    '实际数量': p.actual_quantity,
                    '损耗数量': p.loss_quantity,
                    '日期': p.date.strftime('%Y-%m-%d %H:%M:%S'),
                    '备注': p.notes,
                    '创建时间': p.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    '更新时间': p.updated_at.strftime('%Y-%m-%d %H:%M:%S')
                })
            if product_data:
                pd.DataFrame(product_data).to_excel(writer, sheet_name='产品记录', index=False)
            
            # 导出价格数据
            prices = ProductPrice.query.all()
            price_data = []
            for p in prices:
                price_data.append({
                    'ID': p.id,
                    '商品名称': p.name,
                    '销售价格': p.sale_price,
                    '开始日期': p.start_date.strftime('%Y-%m-%d %H:%M:%S'),
                    '结束日期': p.end_date.strftime('%Y-%m-%d %H:%M:%S') if p.end_date else 'N/A',
                    '创建时间': p.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    '更新时间': p.updated_at.strftime('%Y-%m-%d %H:%M:%S')
                })
            if price_data:
                pd.DataFrame(price_data).to_excel(writer, sheet_name='价格记录', index=False)
            
            # 导出用户数据（不包含密码）
            users = User.query.all()
            user_data = []
            for u in users:
                user_data.append({
                    'ID': u.id,
                    '用户名': u.username,
                    '角色': u.role,
                    '最后登录': u.last_login.strftime('%Y-%m-%d %H:%M:%S') if u.last_login else 'N/A',
                    '创建时间': u.created_at.strftime('%Y-%m-%d %H:%M:%S')
                })
            if user_data:
                pd.DataFrame(user_data).to_excel(writer, sheet_name='用户数据', index=False)
            
            # 导出活动日志
            activities = ActivityLog.query.all()
            activity_data = []
            for a in activities:
                activity_data.append({
                    'ID': a.id,
                    '用户ID': a.user_id,
                    '用户名': a.user.username if a.user else 'N/A',
                    '操作': a.action,
                    '详情': a.details,
                    '创建时间': a.created_at.strftime('%Y-%m-%d %H:%M:%S')
                })
            if activity_data:
                pd.DataFrame(activity_data).to_excel(writer, sheet_name='操作日志', index=False)
        
        output.seek(0)
        
        # 如果已配置S3，则上传Excel备份
        aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        s3_bucket = os.environ.get('S3_BACKUP_BUCKET')
        
        if all([aws_access_key, aws_secret_key, s3_bucket]):
            s3 = boto3.client(
                's3',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key
            )
            
            excel_filename = f"data_backup_{timestamp}.xlsx"
            s3.upload_fileobj(output, s3_bucket, excel_filename)
            logger.info(f"成功导出Excel数据备份到S3: {s3_bucket}/{excel_filename}")
            return True
        else:
            # 保存到本地
            excel_filename = f"data_backup_{timestamp}.xlsx"
            with open(excel_filename, 'wb') as f:
                f.write(output.getvalue())
            logger.info(f"成功导出Excel数据备份到本地: {excel_filename}")
            return True
    
    except Exception as e:
        logger.error(f"Excel备份失败: {str(e)}")
        return False

def backup_to_sql():
    """创建SQL备份文件"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"sql_backup_{timestamp}.sql"
        
        # 获取数据库路径
        db_path = os.environ.get('DATABASE_URL', 'sqlite:///inventory.db')
        
        # 创建一个SQL脚本文件
        with open(backup_filename, 'w', encoding='utf-8') as f:
            # 1. 备份产品数据
            products = Product.query.all()
            f.write("-- 产品数据备份\n")
            for p in products:
                sql = f"""INSERT INTO product (id, name, type, price, quantity, actual_quantity, loss_quantity, date, notes, created_at, updated_at)
VALUES ({p.id}, '{p.name}', '{p.type}', {p.price}, {p.quantity}, {p.actual_quantity}, {p.loss_quantity}, '{p.date.isoformat()}', '{p.notes or ""}', '{p.created_at.isoformat()}', '{p.updated_at.isoformat()}');\n"""
                f.write(sql)
            
            # 2. 备份价格数据
            prices = ProductPrice.query.all()
            f.write("\n-- 价格数据备份\n")
            for p in prices:
                end_date = f"'{p.end_date.isoformat()}'" if p.end_date else "NULL"
                sql = f"""INSERT INTO product_price (id, name, sale_price, start_date, end_date, created_at, updated_at)
VALUES ({p.id}, '{p.name}', {p.sale_price}, '{p.start_date.isoformat()}', {end_date}, '{p.created_at.isoformat()}', '{p.updated_at.isoformat()}');\n"""
                f.write(sql)
            
            # 3. 备份用户数据
            users = User.query.all()
            f.write("\n-- 用户数据备份\n")
            for u in users:
                last_login = f"'{u.last_login.isoformat()}'" if u.last_login else "NULL"
                sql = f"""INSERT INTO user (id, username, password_hash, role, last_login, created_at)
VALUES ({u.id}, '{u.username}', '{u.password_hash}', '{u.role}', {last_login}, '{u.created_at.isoformat()}');\n"""
                f.write(sql)
        
        # 如果已配置S3，则上传SQL备份
        aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        s3_bucket = os.environ.get('S3_BACKUP_BUCKET')
        
        if all([aws_access_key, aws_secret_key, s3_bucket]):
            s3 = boto3.client(
                's3',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key
            )
            
            s3.upload_file(backup_filename, s3_bucket, backup_filename)
            logger.info(f"成功上传SQL备份到S3: {s3_bucket}/{backup_filename}")
            
            # 清理临时文件
            os.remove(backup_filename)
        else:
            logger.info(f"成功创建SQL备份文件: {backup_filename}")
        
        return True
    
    except Exception as e:
        logger.error(f"SQL备份失败: {str(e)}")
        return False

def send_notification(message, success=True):
    """发送通知（如果配置了通知URL）"""
    try:
        notification_url = os.environ.get('BACKUP_NOTIFICATION_URL')
        if not notification_url:
            return
        
        status = "成功" if success else "失败"
        payload = {
            "text": f"数据库备份{status}: {message}",
            "timestamp": datetime.now().isoformat()
        }
        
        response = requests.post(notification_url, json=payload)
        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"通知发送成功")
        else:
            logger.warning(f"通知发送失败: HTTP {response.status_code}")
    
    except Exception as e:
        logger.error(f"发送通知失败: {str(e)}")

def main():
    """主函数：执行所有备份任务"""
    logger.info("开始数据库备份流程")
    
    backup_methods = []
    
    # 读取备份方法配置
    backup_methods_str = os.environ.get('BACKUP_METHODS', 's3,excel,sql')
    if backup_methods_str:
        backup_methods = [m.strip().lower() for m in backup_methods_str.split(',')]
    
    results = []
    
    # 执行备份
    if 's3' in backup_methods:
        s3_result = backup_to_s3()
        results.append(("S3备份", s3_result))
    
    if 'excel' in backup_methods:
        excel_result = export_to_excel()
        results.append(("Excel备份", excel_result))
    
    if 'sql' in backup_methods:
        sql_result = backup_to_sql()
        results.append(("SQL备份", sql_result))
    
    # 汇总结果
    success_count = sum(1 for _, success in results if success)
    total_count = len(results)
    
    if success_count == total_count and total_count > 0:
        message = f"所有{total_count}个备份任务已成功完成"
        logger.info(message)
        send_notification(message)
    elif success_count > 0:
        message = f"部分备份任务完成: {success_count}/{total_count} 成功"
        logger.warning(message)
        send_notification(message, False)
    else:
        message = "所有备份任务均失败"
        logger.error(message)
        send_notification(message, False)

if __name__ == '__main__':
    # 使用适当的应用环境
    from app import app
    with app.app_context():
        main() 