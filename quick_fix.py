import os
import sqlite3
import sys
from datetime import datetime

def quick_fix():
    """快速修复'2025-05-11T19:37:14.519970'格式的日期时间问题"""
    try:
        # 获取数据库路径
        db_path = os.environ.get('DATABASE_URL', 'sqlite:///inventory.db')
        if db_path.startswith('sqlite:///'):
            db_path = db_path[10:]  # 移除 'sqlite:///'
            
        print(f"尝试修复数据库: {db_path}")
        
        # 首先创建数据库备份
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"quick_backup_{timestamp}.sqlite"
        
        # 使用SQLite的备份功能
        conn = sqlite3.connect(db_path)
        backup_conn = sqlite3.connect(backup_path)
        conn.backup(backup_conn)
        backup_conn.close()
        print(f"已创建数据库备份: {backup_path}")
        
        cursor = conn.cursor()
        
        # 直接修复User表中的last_login和created_at字段
        user_fixes = 0
        cursor.execute("SELECT id, last_login, created_at FROM user")
        for user in cursor.fetchall():
            user_id, last_login, created_at = user
            updates = []
            params = []
            
            # 检查并修复last_login
            if last_login and 'T' in str(last_login):
                try:
                    dt = datetime.fromisoformat(str(last_login).replace('Z', '+00:00'))
                    sqlite_dt = dt.strftime('%Y-%m-%d %H:%M:%S.%f')
                    updates.append("last_login = ?")
                    params.append(sqlite_dt)
                    print(f"修复用户 {user_id} 的last_login: {last_login} -> {sqlite_dt}")
                except Exception as e:
                    print(f"处理last_login时出错: {e}")
            
            # 检查并修复created_at
            if created_at and 'T' in str(created_at):
                try:
                    dt = datetime.fromisoformat(str(created_at).replace('Z', '+00:00'))
                    sqlite_dt = dt.strftime('%Y-%m-%d %H:%M:%S.%f')
                    updates.append("created_at = ?")
                    params.append(sqlite_dt)
                    print(f"修复用户 {user_id} 的created_at: {created_at} -> {sqlite_dt}")
                except Exception as e:
                    print(f"处理created_at时出错: {e}")
            
            if updates:
                try:
                    cursor.execute(f"UPDATE user SET {', '.join(updates)} WHERE id = ?", params + [user_id])
                    user_fixes += 1
                except Exception as e:
                    print(f"更新用户 {user_id} 失败: {e}")
        
        # 直接修复ActivityLog表中的created_at字段
        log_fixes = 0
        try:
            cursor.execute("SELECT COUNT(*) FROM activity_log")
            total_logs = cursor.fetchone()[0]
            print(f"总共有 {total_logs} 条活动日志需要检查")
            
            # 分批处理
            batch_size = 500
            for offset in range(0, total_logs, batch_size):
                cursor.execute("SELECT id, created_at FROM activity_log LIMIT ? OFFSET ?", 
                              [batch_size, offset])
                logs = cursor.fetchall()
                
                for log_id, created_at in logs:
                    if created_at and 'T' in str(created_at):
                        try:
                            dt = datetime.fromisoformat(str(created_at).replace('Z', '+00:00'))
                            sqlite_dt = dt.strftime('%Y-%m-%d %H:%M:%S.%f')
                            cursor.execute("UPDATE activity_log SET created_at = ? WHERE id = ?", 
                                          [sqlite_dt, log_id])
                            log_fixes += 1
                            if log_fixes % 100 == 0:
                                print(f"已修复 {log_fixes} 条活动日志记录")
                        except Exception as e:
                            print(f"修复活动日志 {log_id} 失败: {e}")
                
                # 定期提交以避免事务过大
                conn.commit()
                print(f"已处理 {min(offset + batch_size, total_logs)}/{total_logs} 条活动日志记录")
        except Exception as e:
            print(f"处理ActivityLog表时出错: {e}")
        
        # 直接修复Product表中的date, created_at, updated_at字段
        product_fixes = 0
        try:
            cursor.execute("SELECT COUNT(*) FROM product")
            total_products = cursor.fetchone()[0]
            print(f"总共有 {total_products} 条产品记录需要检查")
            
            # 分批处理
            batch_size = 500
            for offset in range(0, total_products, batch_size):
                cursor.execute("SELECT id, date, created_at, updated_at FROM product LIMIT ? OFFSET ?", 
                              [batch_size, offset])
                products = cursor.fetchall()
                
                for product in products:
                    product_id, date, created_at, updated_at = product
                    updates = []
                    params = []
                    
                    # 检查并修复date
                    if date and 'T' in str(date):
                        try:
                            dt = datetime.fromisoformat(str(date).replace('Z', '+00:00'))
                            sqlite_dt = dt.strftime('%Y-%m-%d %H:%M:%S.%f')
                            updates.append("date = ?")
                            params.append(sqlite_dt)
                        except Exception as e:
                            print(f"处理产品 {product_id} 的date时出错: {e}")
                    
                    # 检查并修复created_at
                    if created_at and 'T' in str(created_at):
                        try:
                            dt = datetime.fromisoformat(str(created_at).replace('Z', '+00:00'))
                            sqlite_dt = dt.strftime('%Y-%m-%d %H:%M:%S.%f')
                            updates.append("created_at = ?")
                            params.append(sqlite_dt)
                        except Exception as e:
                            print(f"处理产品 {product_id} 的created_at时出错: {e}")
                    
                    # 检查并修复updated_at
                    if updated_at and 'T' in str(updated_at):
                        try:
                            dt = datetime.fromisoformat(str(updated_at).replace('Z', '+00:00'))
                            sqlite_dt = dt.strftime('%Y-%m-%d %H:%M:%S.%f')
                            updates.append("updated_at = ?")
                            params.append(sqlite_dt)
                        except Exception as e:
                            print(f"处理产品 {product_id} 的updated_at时出错: {e}")
                    
                    if updates:
                        try:
                            cursor.execute(f"UPDATE product SET {', '.join(updates)} WHERE id = ?", 
                                          params + [product_id])
                            product_fixes += 1
                        except Exception as e:
                            print(f"更新产品 {product_id} 失败: {e}")
                
                # 定期提交以避免事务过大
                conn.commit()
                print(f"已处理 {min(offset + batch_size, total_products)}/{total_products} 条产品记录")
        except Exception as e:
            print(f"处理Product表时出错: {e}")
        
        # 直接修复ProductPrice表中的日期字段
        price_fixes = 0
        try:
            cursor.execute("SELECT id, start_date, end_date, created_at, updated_at FROM product_price")
            prices = cursor.fetchall()
            print(f"总共有 {len(prices)} 条价格记录需要检查")
            
            for price in prices:
                price_id, start_date, end_date, created_at, updated_at = price
                updates = []
                params = []
                
                # 检查并修复start_date
                if start_date and 'T' in str(start_date):
                    try:
                        dt = datetime.fromisoformat(str(start_date).replace('Z', '+00:00'))
                        sqlite_dt = dt.strftime('%Y-%m-%d %H:%M:%S.%f')
                        updates.append("start_date = ?")
                        params.append(sqlite_dt)
                    except Exception as e:
                        print(f"处理价格 {price_id} 的start_date时出错: {e}")
                
                # 检查并修复end_date
                if end_date and 'T' in str(end_date):
                    try:
                        dt = datetime.fromisoformat(str(end_date).replace('Z', '+00:00'))
                        sqlite_dt = dt.strftime('%Y-%m-%d %H:%M:%S.%f')
                        updates.append("end_date = ?")
                        params.append(sqlite_dt)
                    except Exception as e:
                        print(f"处理价格 {price_id} 的end_date时出错: {e}")
                
                # 检查并修复created_at
                if created_at and 'T' in str(created_at):
                    try:
                        dt = datetime.fromisoformat(str(created_at).replace('Z', '+00:00'))
                        sqlite_dt = dt.strftime('%Y-%m-%d %H:%M:%S.%f')
                        updates.append("created_at = ?")
                        params.append(sqlite_dt)
                    except Exception as e:
                        print(f"处理价格 {price_id} 的created_at时出错: {e}")
                
                # 检查并修复updated_at
                if updated_at and 'T' in str(updated_at):
                    try:
                        dt = datetime.fromisoformat(str(updated_at).replace('Z', '+00:00'))
                        sqlite_dt = dt.strftime('%Y-%m-%d %H:%M:%S.%f')
                        updates.append("updated_at = ?")
                        params.append(sqlite_dt)
                    except Exception as e:
                        print(f"处理价格 {price_id} 的updated_at时出错: {e}")
                
                if updates:
                    try:
                        cursor.execute(f"UPDATE product_price SET {', '.join(updates)} WHERE id = ?", 
                                      params + [price_id])
                        price_fixes += 1
                    except Exception as e:
                        print(f"更新价格 {price_id} 失败: {e}")
        except Exception as e:
            print(f"处理ProductPrice表时出错: {e}")
        
        # 提交所有更改并关闭连接
        conn.commit()
        conn.close()
        
        print("=" * 40)
        print(f"修复完成! 统计:")
        print(f"- 修复用户记录: {user_fixes}")
        print(f"- 修复活动日志: {log_fixes}")
        print(f"- 修复产品记录: {product_fixes}")
        print(f"- 修复价格记录: {price_fixes}")
        print(f"- 总计修复记录: {user_fixes + log_fixes + product_fixes + price_fixes}")
        print("=" * 40)
        
        return True
    
    except Exception as e:
        print(f"程序执行过程中发生错误: {e}")
        return False

if __name__ == "__main__":
    print("开始修复数据库日期时间格式问题...")
    success = quick_fix()
    if success:
        print("数据库修复成功! 请重启应用程序以应用更改。")
        sys.exit(0)
    else:
        print("数据库修复失败! 请检查错误日志。")
        sys.exit(1) 