import multiprocessing

# 绑定的IP和端口
bind = "127.0.0.1:5000"

# 工作进程数
workers = multiprocessing.cpu_count() * 2 + 1

# 工作模式
worker_class = "sync"

# 最大客户端并发数量
worker_connections = 1000

# 进程名称
proc_name = "vegetable_inventory"

# 进程pid记录文件
pidfile = "gunicorn.pid"

# 访问日志文件
accesslog = "logs/access.log"

# 错误日志文件
errorlog = "logs/error.log"

# 日志级别
loglevel = "info"

# 后台运行
daemon = True

# 重载
reload = True

# 超时时间
timeout = 30

# 最大请求数
max_requests = 2000

# 最大请求抖动
max_requests_jitter = 400 