"""Gunicorn settings, loaded automatically from the working directory (/app).

Without this file Gunicorn runs one synchronous worker with a 30-second timeout.
PDF ingestion runs inside the upload request, and on the Raspberry Pi a normal
document can take longer than that: the worker was killed mid-import, the client
saw a 502, and every other request queued behind the upload meanwhile.

gthread keeps one process (memory is tight on the Pi) but serves other requests
on spare threads during a long upload; the worker heartbeat runs independently of
request threads, so `timeout` only reaps a genuinely hung worker. All values can
be overridden through the environment.
"""
import os

bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:5001")
workers = int(os.environ.get("GUNICORN_WORKERS", "1"))
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "600"))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "30"))
