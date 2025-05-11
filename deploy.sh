#!/bin/bash

# 创建必要的目录
mkdir -p templates static

# 复制所有必要的文件
cp app.py .
cp config.py .
cp requirements.txt .
cp wsgi.py .
cp gunicorn_config.py .
cp render.yaml .

# 复制模板文件
cp -r templates/* templates/
cp -r static/* static/

# 初始化 Git 仓库（如果还没有初始化）
if [ ! -d .git ]; then
    git init
fi

# 添加所有文件到 Git
git add .

# 提交更改
git commit -m "Add template files and update deployment configuration"

# 推送到 GitHub
git push origin master 