# Gunicorn configuration file
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:1551"  # Listen on all interfaces
backlog = 2048

# Worker processes
workers = 3  # Reduced number of workers for stability
worker_class = 'sync'
worker_connections = 1000
timeout = 120
keepalive = 2

# Logging
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "debug"  # More detailed logging

# Process naming
proc_name = "pombot"

# Server mechanics
daemon = False
pidfile = "logs/gunicorn.pid"
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
keyfile = None
certfile = None

# Additional settings
forwarded_allow_ips = '*'  # Allow forwarded requests
proxy_allow_ips = '*'      # Allow proxy requests

# SSL
 