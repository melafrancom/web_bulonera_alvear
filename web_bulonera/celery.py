import os
from celery import Celery

# Configurar el módulo de settings por defecto de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_bulonera.settings.local')

app = Celery('web_bulonera')

# Cargar la configuración de Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-descrubir tareas en todas las aplicaciones registradas
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
