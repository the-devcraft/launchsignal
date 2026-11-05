from rest_framework.response import Response
from rest_framework.views import exception_handler


class Conflict(Exception):
    pass


def handler(exc, context):
    if isinstance(exc, Conflict):
        return Response({"detail": str(exc)}, status=409)
    return exception_handler(exc, context)
