from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.views import exception_handler


# API 명세의 에러 코드용 예외
class ConflictError(APIException):
    """상태가 맞지 않는 요청 (이미 처리된 재고, 확정된 캡처 등)"""

    status_code = status.HTTP_409_CONFLICT
    default_code = "conflict"
    default_detail = "지금은 처리할 수 없는 요청이에요."


class RevertNotAllowed(APIException):
    """취소 불가 (24시간 경과, 이미 취소됨, 이후 다른 처리 있음)"""

    status_code = status.HTTP_409_CONFLICT
    default_code = "revert_not_allowed"
    default_detail = "취소할 수 없는 처리예요."


class InvalidCredentials(APIException):
    """로그인 실패 (이메일·비밀번호 중 어느 쪽인지 구분하지 않음)"""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_code = "invalid_credentials"
    default_detail = "이메일 또는 비밀번호를 확인해 주세요."


class InvalidFile(APIException):
    """파일 형식·용량 위반"""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "invalid_file"
    default_detail = "파일 형식이나 용량을 확인해 주세요."


class ExternalAPIError(APIException):
    """LLM·외부 API 실패로 대체 결과도 없음"""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_code = "external_api_error"
    default_detail = "외부 서비스 응답을 받지 못했어요. 잠시 후 다시 시도해 주세요."


# DRF 기본 예외의 코드·문구를 API 명세에 맞춤
DEFAULT_ERRORS = {
    ValidationError: ("validation_error", "입력값을 확인해 주세요."),
    NotAuthenticated: ("not_authenticated", "로그인이 필요해요."),
    AuthenticationFailed: ("not_authenticated", "로그인이 필요해요."),
    PermissionDenied: ("permission_denied", "권한이 없어요."),
    NotFound: ("not_found", "요청한 정보를 찾을 수 없어요."),
    Throttled: ("too_many_requests", "요청이 너무 많아요. 잠시 후 다시 시도해 주세요."),
}


# 공통 에러 응답 처리기
def custom_exception_handler(exc, context):
    """
    모든 에러 응답을 아래 형식으로 통일합니다.

    {"error": {"code": "...", "message": "...", "fields": {...}}}

    - fields: 입력값 오류(validation_error)일 때만 포함
    - 처리하지 못한 예외(서버 오류 500)는 DRF·Django 기본 처리에 맡김
    """

    # DRF 기본 처리기로 먼저 응답을 만듦 (Http404 → NotFound 변환 등 포함)
    response = exception_handler(exc, context)
    if response is None:
        return None

    # 코드와 문구 결정: 우리 예외 → 명세 매핑 → DRF 기본값 순서
    code, message = getattr(exc, "default_code", "error"), None
    for exc_class, (mapped_code, mapped_message) in DEFAULT_ERRORS.items():
        if isinstance(exc, exc_class):
            code, message = mapped_code, mapped_message
            break

    error = {"code": code}

    if isinstance(exc, ValidationError):
        # 필드별 오류를 fields에 담음 (필드가 없는 오류는 non_field_errors로)
        data = response.data
        error["message"] = message
        error["fields"] = data if isinstance(data, dict) else {"non_field_errors": data}
    else:
        # raise ConflictError("이미 처리된 재료예요.")처럼 직접 넘긴 문구가 있으면 그 문구를 사용
        detail = response.data.get("detail") if isinstance(response.data, dict) else None
        has_custom_detail = detail is not None and str(detail) != str(exc.default_detail)
        error["message"] = str(detail) if has_custom_detail else (message or str(detail))

    response.data = {"error": error}
    return response
