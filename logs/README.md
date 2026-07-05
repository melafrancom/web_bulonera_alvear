# 📁 Directorio logs — Cerebro Local

## 🎯 Propósito
Este directorio centraliza los archivos de logs de ejecución generados por los servicios del servidor web en producción y desarrollo (uWSGI, Django, Celery Workers, Celery Beat). En producción, Docker monta este directorio como un volumen local para permitir persistencia y auditoría de errores desde el host.

## 🕸️ Estructura y Archivos de Logs

```
logs/
├── uwsgi_web.log              ← Logs del servidor de aplicaciones uWSGI (Django views y requests)
├── celery_worker.log          ← Logs del worker Celery (procesamiento asíncrono de imágenes y mails)
├── celery_beat.log            ← Logs del despachador Celery Beat (tareas programadas, indexación, etc.)
└── django_errors.log          ← Logs específicos de excepciones capturadas por Django
```

## 🕸️ Grafo de Origen de Logs

```mermaid
graph TD
    subgraph Docker Container
        uwsgi[uWSGI Application Server] -->|Escribe logs| log_web[logs/uwsgi_web.log]
        worker[Celery Worker] -->|Escribe logs| log_worker[logs/celery_worker.log]
        beat[Celery Beat] -->|Escribe logs| log_beat[logs/celery_beat.log]
    end
    
    subgraph Host Volume
        log_web <.->|Montado en| host_uwsgi[/var/www/bulonera/logs/uwsgi_web.log]
        log_worker <.->|Montado en| host_worker[/var/www/bulonera/logs/celery_worker.log]
        log_beat <.->|Montado en| host_beat[/var/www/bulonera/logs/celery_beat.log]
    end
```

## ⚙️ Configuración y Rotación (log-maxsize)
En `uwsgi.production.ini`, la rotación de logs de uWSGI se maneja de forma automática limitando el tamaño a 10MB:
```ini
logto           = /app/logs/uwsgi_web.log
log-maxsize     = 10485760  ; 10MB
log-master      = true
log-reopen      = true
```

## 📝 Notas de Detalle (Obsidian Vault)
- **Monitoreo en Vivo**: Para monitorear en tiempo real los logs en el VPS, se puede ejecutar desde el host:
  `tail -f /var/www/bulonera/logs/uwsgi_web.log`
- **Ignorado en Git**: Este directorio tiene su contenido ignorado por `.gitignore` y `.dockerignore` para evitar subir logs de ejecución al repositorio de código o incluirlos en el build de Docker.
