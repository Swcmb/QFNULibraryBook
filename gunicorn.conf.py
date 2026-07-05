"""
Gunicorn 配置文件 for QFNU Library Web App
"""
import multiprocessing

bind = "127.0.0.1:8000"
workers = 3
worker_class = "sync"
timeout = 120
graceful_timeout = 30
keepalive = 5

accesslog = "/var/log/qfnu-library/gunicorn-access.log"
errorlog = "/var/log/qfnu-library/gunicorn-error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

proc_name = "qfnu-library"
daemon = False
chdir = "/opt/qfnu-library/web"
wsgi_app = "app:app"

max_requests = 10000
max_requests_jitter = 1000
preload_app = True
