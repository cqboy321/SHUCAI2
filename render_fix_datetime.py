#!/usr/bin/env python3
import os
import sqlite3
import sys
from datetime import datetime
import traceback

def fix_iso_datetime():
    """在Render环境中修复数据库中的ISO格式日期时间"""
    try:
        # 获取数据库路径
        db_path = os.environ.get('DATABASE_URL', 'sqlite:///inventory.db')
        if db_path.startswith('sqlite:///'):
            db_path = db_path[10:]  # 移除 'sqlite:///'
            
        print(f"尝试在Render环境中修复数据库: {db_path}")
        
        # 首先创建数据库备份
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"render_backup_before_fix_{timestamp}.sqlite"
        
        # 使用SQLite的备份功能
        conn = sqlite3.connect(db_path)
        backup_conn = sqlite3.connect(backup_path)
        conn.backup(backup_conn)
        backup_conn.close()
        print(f"已创建数据库备份: {backup_path}")
        
        cursor = conn.cursor()
        
        # 查找所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        # 排除系统表
        tables = [t for t in tables if not t.startswith('sqlite_')]
        print(f"找到的表: {', '.join(tables)}")
        
        # 对每个表进行处理
        total_fixes = 0
        
        for table in tables:
            # 获取表的列结构
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            
            # 寻找可能是日期时间类型的列
            dt_columns = []
            for col in columns:
                col_name = col[1]
                if (
                    col[2].lower() in ('datetime', 'timestamp', 'date') or
                    col_name.lower() in ('created_at', 'updated_at', 'last_login', 'date', 'timestamp', 
                                       'start_date', 'end_date', 'deleted_at', 'accessed_at')
                ):
                    dt_columns.append(col_name)
            
            if not dt_columns:
                print(f"表 {table} 没有找到日期时间列，跳过")
                continue
            
            print(f"处理表 {table}，检查列: {', '.join(dt_columns)}")
            
            # 获取表的行数
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            total_rows = cursor.fetchone()[0]
            
            # 如果表为空，跳过
            if total_rows == 0:
                print(f"表 {table} 为空，跳过")
                continue
            
            print(f"表 {table} 共有 {total_rows} 行数据")
            
            # 分批处理大表
            batch_size = 500
            table_fixes = 0
            
            for offset in range(0, total_rows, batch_size):
                # 构建查询语句
                select_cols = "id, " + ", ".join(dt_columns)
                query = f"SELECT {select_cols} FROM {table} LIMIT ? OFFSET ?"
                
                try:
                    cursor.execute(query, [batch_size, offset])
                    rows = cursor.fetchall()
                    
                    for row in rows:
                        row_id = row[0]
                        updates = []
                        params = []
                        
                        for i, col_name in enumerate(dt_columns, 1):
                            dt_value = row[i]
                            if dt_value and isinstance(dt_value, str) and 'T' in dt_value:
                                try:
                                    # 将ISO格式转换为SQLite兼容格式
                                    dt_obj = datetime.fromisoformat(dt_value.replace('Z', '+00:00'))
                                    new_dt_str = dt_obj.strftime('%Y-%m-%d %H:%M:%S.%f')
                                    updates.append(f"{col_name} = ?")
                                    params.append(new_dt_str)
                                    print(f"修复 {table}.{col_name} (ID={row_id}): {dt_value} -> {new_dt_str}")
                                except Exception as e:
                                    print(f"解析 {table}.{col_name} (ID={row_id}) 时出错: {e}")
                        
                        if updates:
                            try:
                                cursor.execute(
                                    f"UPDATE {table} SET {', '.join(updates)} WHERE id = ?", 
                                    params + [row_id]
                                )
                                table_fixes += 1
                                total_fixes += 1
                            except Exception as e:
                                print(f"更新 {table} (ID={row_id}) 失败: {e}")
                    
                    # 每批次都提交以降低内存使用
                    conn.commit()
                    print(f"已处理 {min(offset + batch_size, total_rows)}/{total_rows} 行 - 表 {table}")
                
                except Exception as e:
                    print(f"处理表 {table} 批次数据时出错: {e}")
                    traceback.print_exc()
            
            print(f"表 {table} 修复完成，共修复 {table_fixes} 行")
        
        # 最终提交并关闭连接
        conn.commit()
        conn.close()
        
        print("=" * 50)
        print(f"全部修复完成! 总共修复 {total_fixes} 行数据")
        print("=" * 50)
        
        return True
    
    except Exception as e:
        print(f"修复过程中发生错误: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Render数据库日期时间格式修复工具")
    print("=" * 50)
    success = fix_iso_datetime()
    if success:
        print("数据库修复成功! 请重启应用服务以应用更改")
        sys.exit(0)
    else:
        print("数据库修复失败! 请检查错误日志")
        sys.exit(1) 