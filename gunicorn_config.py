import multiprocessing
import os

# 工作进程数
workers = multiprocessing.cpu_count() * 2 + 1

# 工作模式
worker_class = 'sync'

# 绑定地址
bind = f"0.0.0.0:{os.getenv('PORT', '10000')}"

# 超时设置
timeout = 120

# 访问日志
accesslog = '-'

# 错误日志
errorlog = '-'

# 日志级别
loglevel = 'info'

# 预加载应用
preload_app = True

# 守护进程
daemon = False

# 最大客户端并发数量
worker_connections = 1000

# 进程名称
proc_name = "vegetable_inventory"

# 进程pid记录文件
pidfile = "gunicorn.pid"

# 重载
reload = True

# 最大请求数
max_requests = 2000

# 最大请求抖动
max_requests_jitter = 400 