#!/usr/bin/env python
"""
创建价格导入模板Excel文件
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

# 创建示例数据
vegetables = ['空心菜', '水白菜', '水萝卜', '油麦菜', '菜心', '塔菜', '白萝卜', '快白菜', '小白菜', '大白菜']
data = []

# 今天和明天的日期
today = datetime.now()
tomorrow = today + timedelta(days=1)
next_week = today + timedelta(days=7)

# 为每种蔬菜创建一个示例行
for vegetable in vegetables:
    # 生成随机价格示例，保留两位小数
    price = round(np.random.uniform(8.0, 15.0), 2)
    
    # 随机使用不同的日期格式和组合
    data.append({
        '商品名称': vegetable,
        '销售价格': price,
        '开始日期': today.strftime('%Y-%m-%d'),
        '结束日期': next_week.strftime('%Y-%m-%d') if np.random.choice([True, False]) else None
    })

# 创建DataFrame
df = pd.DataFrame(data)

# 添加一行示例说明
example = {
    '商品名称': '示例说明',
    '销售价格': 0,
    '开始日期': '必填，日期格式',
    '结束日期': '选填，留空表示永久有效'
}
df = pd.concat([pd.DataFrame([example]), df], ignore_index=True)

# 确保目录存在
os.makedirs('static/templates', exist_ok=True)
output_path = 'static/templates/price_template.xlsx'

# 使用上下文管理器创建Excel文件
with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
    df.to_excel(writer, sheet_name='价格导入模板', index=False)
    
    # 获取工作簿和工作表对象
    workbook = writer.book
    worksheet = writer.sheets['价格导入模板']
    
    # 设置列宽
    worksheet.set_column('A:A', 15)  # 商品名称
    worksheet.set_column('B:B', 10)  # 销售价格
    worksheet.set_column('C:D', 15)  # 日期字段
    
    # 添加格式
    header_format = workbook.add_format({
        'bold': True,
        'text_wrap': True,
        'valign': 'top',
        'align': 'center',
        'fg_color': '#D7E4BC',
        'border': 1
    })
    
    # 对于列标题应用格式
    for col_num, value in enumerate(df.columns.values):
        worksheet.write(0, col_num, value, header_format)
    
    # 添加说明行的格式
    example_format = workbook.add_format({
        'italic': True,
        'font_color': 'red',
        'bg_color': '#F2F2F2'
    })
    
    # 对示例说明行应用格式
    for col_num in range(len(df.columns)):
        worksheet.write(1, col_num, df.iloc[0, col_num], example_format)

print(f"已创建价格模板文件: {output_path}") 