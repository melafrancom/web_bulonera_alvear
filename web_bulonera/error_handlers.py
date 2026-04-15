"""Custom error handlers for Django"""
from django.shortcuts import render


def handler404(request, exception=None):
    """Handler para errores 404 - Página no encontrada"""
    return render(request, 'errors/404.html', status=404)


def handler500(request):
    """Handler para errores 500 - Error del servidor"""
    return render(request, 'errors/500.html', status=500)


def handler403(request, exception=None):
    """Handler para errores 403 - Acceso denegado"""
    return render(request, 'errors/403.html', status=403)


def handler400(request, exception=None):
    """Handler para errores 400 - Solicitud incorrecta"""
    return render(request, 'errors/400.html', status=400)
