#!/bin/bash

# 创建必要的目录
mkdir -p templates static

# 复制模板文件
cp -r templates/* templates/

# 复制静态文件（如果有）
if [ -d "static" ]; then
    cp -r static/* static/
fi

# 安装依赖
pip install -r requirements.txt

# 启动应用
gunicorn wsgi:app -c gunicorn_config.py 