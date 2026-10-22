import os

bind = '0.0.0.0:8000'
workers = int(os.environ.get('HR_WEB_WORKERS', '2'))
threads = 2
worker_class = 'gthread'
timeout = 90
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
preload_app = False
worker_tmp_dir = '/tmp'
accesslog = '-'
errorlog = '-'
# Do not log query strings, referrers, request bodies, cookies or credentials.
access_log_format = '%(h)s %(m)s %(U)s %(s)s %(D)s'
forwarded_allow_ips = '*'
