from django.http import Http404
from django.core.exceptions import PermissionDenied,ValidationError
from rest_framework import exceptions
from rest_framework.views import set_rollback,Response,exception_handler

def custom_exception_handler(exc, context):

    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()
    elif isinstance(exc, ValidationError):
        if hasattr(exc, 'message_dict'):  # Nếu có message_dict (là dict)
            exc = exceptions.ValidationError({'status': 'error', 'error': exc.message_dict})
        elif hasattr(exc, 'messages'):  # Nếu là danh sách message
            exc = exceptions.ValidationError({'status': 'error', 'error': exc.messages})
        else:  # Nếu chỉ có một message dạng string
            exc = exceptions.ValidationError({'status': 'error', 'error': str(exc)})

    if isinstance(exc, exceptions.APIException):
        headers = {}
        if getattr(exc, 'auth_header', None):
            headers['WWW-Authenticate'] = exc.auth_header
        if getattr(exc, 'wait', None):
            headers['Retry-After'] = '%d' % exc.wait

        if isinstance(exc.detail, (list, dict)):
            data = exc.detail
        else:
            data = {'detail': exc.detail}

        set_rollback()
        return Response(data, status=exc.status_code, headers=headers)

    return None