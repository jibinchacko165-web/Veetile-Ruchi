import os
import multiprocessing

# Bind to Zoho Catalyst dynamic port or default to 8000
port = os.environ.get('X_ZOHO_CATALYST_LISTEN_PORT', os.environ.get('PORT', '8000'))
bind = f"0.0.0.0:{port}"

# Concurrency & Worker model
workers = int(os.environ.get('WEB_CONCURRENCY', min(multiprocessing.cpu_count() * 2 + 1, 4)))
threads = int(os.environ.get('PYTHON_MAX_THREADS', '2'))
worker_class = 'gthread'

# Reliability & Timeouts
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '120'))
graceful_timeout = int(os.environ.get('GUNICORN_GRACEFUL_TIMEOUT', '30'))
keepalive = int(os.environ.get('GUNICORN_KEEPALIVE', '5'))

# Memory & Process recycling
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('LOG_LEVEL', 'info')
