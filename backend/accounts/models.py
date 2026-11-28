from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


# 시·군·구 기준 목록
class Region(models.Model):
    """
    시·군·구 관련 데이터를 저장합니다.

    - region_code: 시·군·구 코드
    - sido_name: 시·도명 (예: 서울특별시)
    - sigungu_name: 시·군·구명 (예: 종로구)
    - is_active: 사용 여부
    """

    # 필드 정의
    region_code = models.CharField(max_length=5, primary_key=True)
    sido_name = models.CharField(max_length=20)
    sigungu_name = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)

    # 데이터베이스 정의
    class Meta:
        db_table = "region"
        ordering = ["sido_name", "sigungu_name"]

    def __str__(self):
        return f"{self.sido_name} {self.sigungu_name}"


# 이메일 로그인 User 생성 매니저
class UserManager(BaseUserManager):
    """
    이메일을 로그인 아이디로 쓰는 User를 생성합니다.

    - create_user: 일반 사용자 생성 (이메일 필수, 비밀번호는 해시로 저장)
    - create_superuser: 관리자 생성 (is_staff, is_superuser=True)
    """

    # 마이그레이션에서도 해당 매니저를 사용하도록 설정
    use_in_migrations = True

    # 일반 사용자 생성 함수
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("이메일은 필수입니다.")

        # 도메인 부분을 소문자로 정리
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)

        # 비밀번호는 해시로 저장
        user.set_password(password)
        user.save(using=self._db)

        return user

    # 관리자 생성 함수
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(email, password, **extra_fields)


# 커스텀 User (로그인 + 프로필)
class User(AbstractUser):
    """
    로그인 정보와 프로필을 함께 저장합니다.
    이메일로 로그인하고, 화면에는 닉네임을 표시합니다.

    - email: 로그인 이메일 (탈퇴 시 NULL)
    - password: 비밀번호 해시 (Django 기본 값)
    - nickname: 닉네임
    - profile_image_path: 프로필 이미지 경로 (외부 스토리지, 없으면 빈 문자열)
    - bio: 한 줄 소개 (없으면 빈 문자열)
    - household_size: 가구 인원 (추천 인분에 참고할 값)
    - preferred_cuisines: 선호 요리 종류 (예: ["국&찌개", "반찬"], 기본값: [])
    - region: 활동 지역 (시·군·구, DB 컬럼명: region_code)
    - is_public: 프로필 공개 여부 (기본값: True)
    - is_active: 활성화 여부 (탈퇴 시 False)
    - is_staff: 관리자 화면 접근 (Django 기본 값)
    - is_superuser: 최고 관리자 (Django 기본 값)
    - date_joined: 가입 시각
    - last_login: 마지막 로그인
    - withdrawn_at: 탈퇴 시각
    """

    # 사용하지 않는 기본 필드 제거
    username = None
    first_name = None
    last_name = None

    # 필드 정의
    # unique 값이라 빈 문자열 대신 NULL 사용
    email = models.EmailField(max_length=254, unique=True, null=True)  # noqa: DJ001
    nickname = models.CharField(max_length=20, unique=True)
    profile_image_path = models.CharField(max_length=300, blank=True, default="")
    bio = models.CharField(max_length=100, blank=True, default="")
    household_size = models.PositiveSmallIntegerField(null=True, blank=True)
    preferred_cuisines = models.JSONField(default=list, blank=True)
    region = models.ForeignKey(
        Region,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="region_code",
        related_name="users",
    )
    is_public = models.BooleanField(default=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    # 로그인 설정
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nickname"]

    # 매니저 연결
    objects = UserManager()

    # 데이터베이스 정의
    class Meta:
        db_table = "users"

    def __str__(self):
        return self.nickname
