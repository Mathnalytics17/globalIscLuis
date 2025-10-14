from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException


def custom_exception_handler(exc, context):

    response = exception_handler(exc, context)

    if response is not None:
        response.data['code'] = response.status_code

        #replace detail key with message key by delete detail key
        response.data['message'] = response.data['detail']
        del response.data['detail']

    return response


class HttpException(APIException):

    #public fields
    detail = None
    status_code = None

    # create constructor
    def __init__(self, status_code, message):
        #override public fields
        HttpException.status_code = status_code
        HttpException.detail = message
