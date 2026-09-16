import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('django')


class ErrorLoggingMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        logger.error(
            "Unhandled exception on %s %s",
            request.method,
            request.path,
            exc_info=exception,
        )
        return None
