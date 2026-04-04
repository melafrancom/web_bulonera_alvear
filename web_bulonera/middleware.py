import logging
from django.utils.deprecation import MiddlewareMixin

class ErrorLoggingMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        logging.error(f"Error processing request: {request.path}", exc_info=exception)
        return None
