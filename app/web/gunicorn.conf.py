import os

bind = "0.0.0.0:8080"
workers = 1
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
timeout = 30
graceful_timeout = 20
keepalive = 5
accesslog = None
worker_tmp_dir = "/dev/shm" if os.path.isdir("/dev/shm") else None


def post_worker_init(worker):
    from config import telemetria

    telemetria.configurar_logs()
