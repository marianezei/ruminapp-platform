import os

from django.core.wsgi import get_wsgi_application

from config import telemetria

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

telemetria.configurar_traces()
telemetria.iniciar_metricas()

application = get_wsgi_application()
