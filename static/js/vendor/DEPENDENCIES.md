# Frontend Dependencies (Self-hosted)

Este directorio contiene las bibliotecas de frontend ancladas a versiones estables para evitar warnings de tracking, mejorar la velocidad de carga (eliminar DNS lookup y conexiones TLS de terceros) y dar soporte 100% offline a la PWA.

| Library | Version | Source | Last Updated |
|---|---|---|---|
| Alpine.js | 3.14.9 | jsdelivr | 2026-07-07 |
| Alpine Collapse | 3.14.9 | jsdelivr | 2026-07-07 |
| Lucide Icons | 0.468.0 | unpkg | 2026-07-07 |

## Update Process
1. Check releases: https://github.com/alpinejs/alpine/releases
2. Download new version to `static/js/vendor/`
3. Update filename references in `base.html`
4. Test locally using `docker-compose exec bulonera_web python manage.py check` and `pytest`
5. Deploy
