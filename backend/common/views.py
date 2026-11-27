from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


# 서버 상태 확인
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """
    서버가 동작하는지 확인합니다. (로그인 없이 호출 가능)

    - 응답: {"status": "ok"}
    """

    return Response({"status": "ok"})
