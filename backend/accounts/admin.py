from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Region, User


# 시·군·구 관리 화면
@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    """
    시·군·구 목록을 조회·수정합니다.
    """

    # 목록 화면 설정
    list_display = ("region_code", "sido_name", "sigungu_name", "is_active")
    list_filter = ("sido_name", "is_active")
    search_fields = ("region_code", "sido_name", "sigungu_name")


# 사용자 관리 화면
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    이메일 로그인 User에 맞춘 관리 화면입니다.
    (기본 UserAdmin은 username 기준이라 이메일·닉네임 기준으로 다시 구성)
    """

    # 목록 화면 설정
    list_display = ("id", "email", "nickname", "region", "is_public", "is_active", "is_staff")
    list_filter = ("is_active", "is_staff", "is_public")
    search_fields = ("email", "nickname")
    ordering = ("id",)

    # 상세(수정) 화면 구성
    fieldsets = (
        ("로그인 정보", {"fields": ("email", "password")}),
        (
            "프로필",
            {
                "fields": (
                    "nickname",
                    "profile_image_path",
                    "bio",
                    "household_size",
                    "preferred_cuisines",
                    "region",
                    "is_public",
                )
            },
        ),
        (
            "권한",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("기록", {"fields": ("last_login", "date_joined", "withdrawn_at")}),
    )

    # 사용자 추가 화면 구성
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "nickname", "password1", "password2"),
            },
        ),
    )
