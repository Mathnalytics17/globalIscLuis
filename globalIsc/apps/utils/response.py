from rest_framework.response import Response
from rest_framework import status as http_status


def response(data, status):
    try:
        if status == 200:
            return Response(data, status=http_status.HTTP_200_OK)
        elif status == 201:
            return Response(data, status=http_status.HTTP_201_CREATED)
        elif status == 204:
            return Response(data, status=http_status.HTTP_204_NO_CONTENT)
        elif status == 400:
            return Response(data, status=http_status.HTTP_400_BAD_REQUEST)
        elif status == 401:
            return Response(data, status=http_status.HTTP_401_UNAUTHORIZED)
        elif status == 403:
            return Response(data, status=http_status.HTTP_403_FORBIDDEN)
        elif status == 404:
            return Response(data, status=http_status.HTTP_404_NOT_FOUND)
        elif status == 405:
            return Response(data, status=http_status.HTTP_405_METHOD_NOT_ALLOWED)
        elif status == 500:
            return Response(data, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        return Response({'error': True, 'message': str(e)}, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)
