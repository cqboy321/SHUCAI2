import os
import sqlite3
import logging
from datetime import datetime
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def fix_datetime_format():
    """修复数据库中的日期时间格式问题"""
    try:
        # 获取数据库路径
        db_path = os.environ.get('DATABASE_URL', 'sqlite:///inventory.db')
        if db_path.startswith('sqlite:///'):
            db_path = db_path[10:]  # 移除 'sqlite:///'
            
        logger.info(f"尝试修复数据库: {db_path}")
        
        # 首先创建数据库备份
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"auto_backup_before_fix_{timestamp}.sqlite"
        
        try:
            # 使用SQLite的备份功能
            conn = sqlite3.connect(db_path)
            backup_conn = sqlite3.connect(backup_path)
            conn.backup(backup_conn)
            backup_conn.close()
            logger.info(f"已创建数据库备份: {backup_path}")
        except Exception as e:
            logger.error(f"创建备份失败: {str(e)}")
            return False
        
        # 修复User表的last_login和created_at字段
        cursor = conn.cursor()
        
        # 检查User表中的日期时间字段
        cursor.execute("PRAGMA table_info(user)")
        columns = cursor.fetchall()
        datetime_columns = []
        for col in columns:
            if col[2].lower() in ('datetime', 'timestamp'):
                datetime_columns.append(col[1])
        
        # 如果没有找到日期时间字段，尝试常见的字段名
        if not datetime_columns:
            datetime_columns = ['last_login', 'created_at']
        
        logger.info(f"需要修复的日期时间字段: {', '.join(datetime_columns)}")
        
        # 获取用户表中的所有记录
        cursor.execute("SELECT id, " + ", ".join(datetime_columns) + " FROM user")
        users = cursor.fetchall()
        
        fixed_count = 0
        for user in users:
            user_id = user[0]
            updates = []
            params = []
            
            for i, col_name in enumerate(datetime_columns, 1):
                dt_value = user[i]
                if dt_value and ('T' in str(dt_value) or 'Z' in str(dt_value)):
                    try:
                        # 尝试解析ISO格式的日期时间
                        if 'T' in str(dt_value):
                            # 如果是ISO格式 (例如 '2025-05-11T19:37:14.519970')
                            dt_obj = datetime.fromisoformat(str(dt_value).replace('Z', '+00:00'))
                            new_dt_str = dt_obj.strftime('%Y-%m-%d %H:%M:%S.%f')
                            updates.append(f"{col_name} = ?")
                            params.append(new_dt_str)
                            logger.info(f"修复用户ID {user_id} 的 {col_name}: {dt_value} -> {new_dt_str}")
                    except Exception as e:
                        logger.error(f"解析日期时间失败 ({user_id}.{col_name}): {dt_value} - {str(e)}")
            
            if updates:
                try:
                    cursor.execute(
                        f"UPDATE user SET {', '.join(updates)} WHERE id = ?", 
                        params + [user_id]
                    )
                    fixed_count += 1
                except Exception as e:
                    logger.error(f"更新用户 {user_id} 失败: {str(e)}")
        
        # 检查ProductPrice表
        cursor.execute("PRAGMA table_info(product_price)")
        columns = cursor.fetchall()
        datetime_columns = []
        for col in columns:
            if col[2].lower() in ('datetime', 'timestamp'):
                datetime_columns.append(col[1])
        
        if datetime_columns:
            logger.info(f"修复ProductPrice表中的日期字段: {', '.join(datetime_columns)}")
            cursor.execute("SELECT id, " + ", ".join(datetime_columns) + " FROM product_price")
            prices = cursor.fetchall()
            
            for price in prices:
                price_id = price[0]
                updates = []
                params = []
                
                for i, col_name in enumerate(datetime_columns, 1):
                    dt_value = price[i]
                    if dt_value and ('T' in str(dt_value) or 'Z' in str(dt_value)):
                        try:
                            if 'T' in str(dt_value):
                                dt_obj = datetime.fromisoformat(str(dt_value).replace('Z', '+00:00'))
                                new_dt_str = dt_obj.strftime('%Y-%m-%d %H:%M:%S.%f')
                                updates.append(f"{col_name} = ?")
                                params.append(new_dt_str)
                                logger.info(f"修复价格ID {price_id} 的 {col_name}: {dt_value} -> {new_dt_str}")
                        except Exception as e:
                            logger.error(f"解析日期时间失败 ({price_id}.{col_name}): {dt_value} - {str(e)}")
                
                if updates:
                    try:
                        cursor.execute(
                            f"UPDATE product_price SET {', '.join(updates)} WHERE id = ?", 
                            params + [price_id]
                        )
                    except Exception as e:
                        logger.error(f"更新价格 {price_id} 失败: {str(e)}")
        
        # 检查Product表
        cursor.execute("PRAGMA table_info(product)")
        columns = cursor.fetchall()
        datetime_columns = []
        for col in columns:
            if col[2].lower() in ('datetime', 'timestamp'):
                datetime_columns.append(col[1])
        
        if datetime_columns:
            logger.info(f"修复Product表中的日期字段: {', '.join(datetime_columns)}")
            
            # 分批处理Product表，防止内存溢出
            cursor.execute("SELECT COUNT(*) FROM product")
            total_products = cursor.fetchone()[0]
            batch_size = 500
            
            for offset in range(0, total_products, batch_size):
                cursor.execute(
                    f"SELECT id, {', '.join(datetime_columns)} FROM product LIMIT ? OFFSET ?", 
                    [batch_size, offset]
                )
                products = cursor.fetchall()
                
                for product in products:
                    product_id = product[0]
                    updates = []
                    params = []
                    
                    for i, col_name in enumerate(datetime_columns, 1):
                        dt_value = product[i]
                        if dt_value and ('T' in str(dt_value) or 'Z' in str(dt_value)):
                            try:
                                if 'T' in str(dt_value):
                                    dt_obj = datetime.fromisoformat(str(dt_value).replace('Z', '+00:00'))
                                    new_dt_str = dt_obj.strftime('%Y-%m-%d %H:%M:%S.%f')
                                    updates.append(f"{col_name} = ?")
                                    params.append(new_dt_str)
                            except Exception as e:
                                logger.error(f"解析日期时间失败 ({product_id}.{col_name}): {dt_value} - {str(e)}")
                    
                    if updates:
                        try:
                            cursor.execute(
                                f"UPDATE product SET {', '.join(updates)} WHERE id = ?", 
                                params + [product_id]
                            )
                        except Exception as e:
                            logger.error(f"更新产品 {product_id} 失败: {str(e)}")
        
        # 检查ActivityLog表
        cursor.execute("PRAGMA table_info(activity_log)")
        columns = cursor.fetchall()
        datetime_columns = []
        for col in columns:
            if col[2].lower() in ('datetime', 'timestamp'):
                datetime_columns.append(col[1])
        
        if datetime_columns:
            logger.info(f"修复ActivityLog表中的日期字段: {', '.join(datetime_columns)}")
            
            # 分批处理ActivityLog表
            cursor.execute("SELECT COUNT(*) FROM activity_log")
            total_logs = cursor.fetchone()[0]
            batch_size = 500
            
            for offset in range(0, total_logs, batch_size):
                cursor.execute(
                    f"SELECT id, {', '.join(datetime_columns)} FROM activity_log LIMIT ? OFFSET ?", 
                    [batch_size, offset]
                )
                logs = cursor.fetchall()
                
                for log in logs:
                    log_id = log[0]
                    updates = []
                    params = []
                    
                    for i, col_name in enumerate(datetime_columns, 1):
                        dt_value = log[i]
                        if dt_value and ('T' in str(dt_value) or 'Z' in str(dt_value)):
                            try:
                                if 'T' in str(dt_value):
                                    dt_obj = datetime.fromisoformat(str(dt_value).replace('Z', '+00:00'))
                                    new_dt_str = dt_obj.strftime('%Y-%m-%d %H:%M:%S.%f')
                                    updates.append(f"{col_name} = ?")
                                    params.append(new_dt_str)
                            except Exception as e:
                                logger.error(f"解析日期时间失败 ({log_id}.{col_name}): {dt_value} - {str(e)}")
                    
                    if updates:
                        try:
                            cursor.execute(
                                f"UPDATE activity_log SET {', '.join(updates)} WHERE id = ?", 
                                params + [log_id]
                            )
                        except Exception as e:
                            logger.error(f"更新日志 {log_id} 失败: {str(e)}")
        
        # 提交更改并关闭连接
        conn.commit()
        conn.close()
        
        logger.info(f"修复完成，已修复 {fixed_count} 条记录")
        return True
    
    except Exception as e:
        logger.error(f"修复过程中发生错误: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("开始修复数据库日期时间格式...")
    success = fix_datetime_format()
    if success:
        logger.info("数据库修复成功！")
    else:
        logger.error("数据库修复失败！") 