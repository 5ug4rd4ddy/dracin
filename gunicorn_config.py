import multiprocessing
import os

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
threads = 2
timeout = 120
accesslog = "-"
errorlog = "-"
loglevel = "info"
worker_class = "gthread"
keepalive = 5

# Reload code in development (opsional, matikan di production)
reload = False
