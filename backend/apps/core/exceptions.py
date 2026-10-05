"""API exception handling: map domain errors to consistent HTTP responses."""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The request conflicts with the current state of the resource."
    default_code = "conflict"


def exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        detail = exc.message_dict if hasattr(exc, "error_dict") else {"detail": exc.messages}
        exc = ValidationError(detail=detail)
    elif isinstance(exc, ProtectedError):
        exc = Conflict("This record is referenced by other records and cannot be deleted.")
    elif isinstance(exc, IntegrityError):
        # Constraint violations that slipped past serializer validation (e.g. races).
        return Response(
            {"detail": "The data violates a uniqueness or integrity rule. It may already exist."},
            status=status.HTTP_409_CONFLICT,
        )
    return drf_exception_handler(exc, context)
