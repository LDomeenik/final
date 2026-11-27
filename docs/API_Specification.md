# API 명세서

```
본 문서는 기능 명세서의 기능 ID별로 REST API의 경로, 메서드, 요청·응답 형식, 에러를 정의합니다.
백엔드(Django + DRF)와 프론트엔드(Vue 3)는 이 문서를 기준으로 동시에 작업합니다.

P0(핵심 흐름)은 요청·응답 예시까지 정의하고,
P1은 경로·주요 파라미터·응답 필드를 정의한 뒤 구현하면서 예시를 채웁니다.
테이블·컬럼은 데이터 명세서를, 동작 규칙은 기능 명세서를 따릅니다.
명세를 바꿀 때는 이 문서를 먼저 고치고 상대에게 알립니다.
```

---

## Table of contents

- [0. 공통 규칙](#0-공통-규칙)
- [1. 엔드포인트 목록](#1-엔드포인트-목록)
- [2. P0 상세](#2-p0-상세)
  - [2.1 회원 (AUTH)](#21-회원-auth)
  - [2.2 기준 데이터](#22-기준-데이터)
  - [2.3 재고 (INV)](#23-재고-inv)
  - [2.4 레시피·추천 (REC)](#24-레시피추천-rec)
  - [2.5 점수 피드백 (SCR-01)](#25-점수-피드백-scr-01)
- [3. P1 요약](#3-p1-요약)
- [4. 관리 명령·배치](#4-관리-명령배치)
- [5. 확장 시 변경 예정](#5-확장-시-변경-예정)

---

## 0. 공통 규칙

### 0.1 인증

| 항목 | 규칙 |
| :--- | --- |
| 방식 | DRF 기본 토큰 (`rest_framework.authtoken`), 회원 API는 직접 구현 |
| 헤더 | `Authorization: Token {token}` |
| 만료 | MVP에서는 만료 없음 (로그아웃 시 토큰 삭제) |
| 비회원 허용 | 표의 인증 칸이 `없음`인 API만 토큰 없이 호출, `선택`은 토큰이 있으면 회원 기준으로 응답 |
| 실패 | 토큰이 없거나 유효하지 않으면 `401` → 프론트는 로그인 화면으로 이동 |

- 프론트는 토큰 저장, 헤더 추가, 401 처리를 `api/` 모듈의 공통 설정(axios 인터셉터) 한 곳에서만 처리합니다. (확장 시 JWT로 바꿀 때 이 부분만 수정)

### 0.2 에러 응답

모든 에러는 같은 형식으로 응답합니다. (DRF 커스텀 예외 처리기로 통일)

```json
{
  "error": {
    "code": "validation_error",
    "message": "입력값을 확인해 주세요.",
    "fields": {
      "nickname": ["이미 사용 중인 닉네임이에요."]
    }
  }
}
```

- `fields`는 `validation_error`일 때만 포함하며, 배열 안의 항목은 `items.1.quantity`처럼 위치로 표시합니다.
- `message`는 화면에 그대로 보여줄 수 있는 문구입니다.

| HTTP | code | 상황 |
| :---: | --- | --- |
| 400 | `validation_error` | 입력값 오류 |
| 400 | `invalid_file` | 파일 형식·용량 위반 |
| 401 | `not_authenticated` | 토큰이 없거나 유효하지 않음 |
| 401 | `invalid_credentials` | 로그인 실패 (이메일·비밀번호 구분 없음, 탈퇴 계정 포함) |
| 403 | `permission_denied` | 작성자가 아님 등 권한 없음 |
| 404 | `not_found` | 없는 리소스, 다른 사용자의 재고·캡처·추천 |
| 409 | `conflict` | 상태가 맞지 않는 요청 (이미 확정된 캡처, 이미 처리된 재고, 완료된 거래 등) |
| 409 | `revert_not_allowed` | 취소 불가 (24시간 경과, 이미 취소됨, 이후 다른 처리 있음) |
| 429 | `too_many_requests` | 호출 횟수 제한 초과 (비회원 API) |
| 502 | `external_api_error` | LLM·외부 API 실패로 대체 결과도 없음 |

### 0.3 목록 페이지 나누기

| 방식 | 대상 | 요청 | 응답 |
| :--- | --- | --- | --- |
| 커서 (무한 스크롤) | 피드, 나눔 목록, 알림, 점수 내역, 팔로워·팔로잉 | `?cursor={next}` | `{ "results": [...], "next": "cD0yMDI2...", "has_next": true }` |
| 페이지 번호 | 레시피 검색, 비회원 레시피 결과 | `?page=1` | `{ "results": [...], "count": 132, "page": 1, "next": 2, "has_next": true }` |
| 나누지 않음 | 댓글, 시·군·구, 재료 그룹, 냉장고 재고 | — | `{ "results": [...] }` |

- `next`가 `null`이면 마지막입니다. (커서 방식은 다음 커서 값, 페이지 방식은 다음 페이지 번호)
- 한 번에 가져오는 개수: 피드·나눔 10개, 알림·점수 내역·팔로워 20개, 레시피 12개

### 0.4 주소 규칙

- Base URL `/api/v1`, 복수형 명사, 단어는 하이픈, 끝에 `/` (예: `/api/v1/inventory-items/`)
- 조회 `GET`, 생성 `POST`, 단순 수정 `PATCH`, 삭제 `DELETE`
- 재고 이벤트·점수·알림이 따라오는 동작은 하위 경로 동사로 `POST` (예: `POST /inventory-items/{id}/discard/`)

### 0.5 형식

| 항목 | 규칙 |
| :--- | --- |
| 필드 이름 | snake_case (데이터 명세서 컬럼명과 맞춤) |
| 시각 | ISO 8601, 한국 시간 오프셋 포함 (`2026-11-27T11:34:00+09:00`) |
| 날짜 | `YYYY-MM-DD` |
| 금액 | 원 단위 정수, 가격 미입력은 `null` |
| 수량 | 숫자 (소수 둘째 자리까지), presence 재료는 `null` |
| 표시용 값 | 남은 일수, 임박 상태, 수량 단계, 냉장고 칸 등은 서버가 계산해서 함께 응답 |

- **화면 표시 형식**: 프론트는 시각을 `2026-11-27 11:34`, 날짜를 `2026-11-27`로 표시합니다. (공통 함수 `formatDateTime`, `formatDate`)

### 0.6 이미지 업로드

- 게시글·프로필·레시피 단계 사진은 **먼저 업로드**하고, 작성·수정 API에는 받은 `image_path`만 보냅니다.
- 캡처는 인식을 바로 해야 하므로 `POST /captures/`에 파일을 직접 보냅니다.
- 개발 환경은 Django media 폴더에 저장하고, 배포 저장소는 배포 환경을 정할 때 결정합니다.
- 업로드만 하고 쓰지 않은 이미지는 정리 배치로 삭제합니다. (확장)

### 0.7 공통 객체

**score**: 점수가 바뀌는 API 응답에 포함 (SCR-01)

```json
{
  "score": {
    "delta": 8,
    "reason": "임박 재료 2개 소진",
    "current_score": 72,
    "capped": false
  }
}
```

- 점수 변화가 없으면 `"score": null`
- `capped`: 하루 가점 상한으로 잘렸으면 `true` (화면에 "오늘 가점 상한 도달" 표시)
- 여러 규칙이 함께 적용되면 `delta`는 합계, `reason`은 대표 사유 1개

**badges_earned**: 뱃지를 판정하는 API 응답에 포함 (없으면 빈 배열)

```json
{ "badges_earned": [{ "code": "first_capture", "name": "첫 캡처 등록", "icon": "badge_first_capture" }] }
```

**quantity**: 재고 수량 표시용

```json
{ "mode": "amount", "remaining": 600, "initial": 1000, "unit": "ml", "level": "many", "text": "많음" }
```

- `mode`: `count`(개수) / `amount`(양) / `presence`(있음)
- `level`: amount만 사용, `many`(남은 비율 0.6 이상) / `half`(0.3 이상) / `little`(0.3 미만)
- `text`: 화면 표시 문구 (`"3개"`, `"많음"`, `"있음"`)

**expiry**: 소비기한 표시용

```json
{ "expected_date": "2026-11-29", "days_left": 2, "status": "expiring", "source": "auto" }
```

- `days_left`: 오늘(한국 시간) 기준 남은 일수, 지나면 음수
- `status`: `ok`(4일 이상) / `expiring`(0~3일) / `expired`(지남) / `check_needed`(지남 + 확인 응답 필요)
- `source`: `auto` / `manual` (직접 수정한 소비기한)

**zone**: 냉장고 그림의 칸 (서버가 보관 위치 + 재료 그룹 분류로 계산)

| 값 | 칸 | 규칙 |
| :--- | --- | --- |
| `freezer` | 냉동칸 | storage = freezer |
| `fridge_shelf` | 냉장 선반 | storage = fridge, 아래 두 분류가 아닌 재료 |
| `vegetable` | 채소칸 | storage = fridge, 분류가 채소·과일 |
| `door` | 도어 | storage = fridge, 분류가 음료·소스·양념 |
| `room_shelf` | 실온 선반 | storage = room |

---

## 1. 엔드포인트 목록

| 기능 ID | 메서드 | 경로 | 설명 | 인증 | 우선 |
| :--- | :---: | --- | --- | :---: | :---: |
| AUTH-01 | POST | `/auth/signup/` | 회원가입 | 없음 | P0 |
| AUTH-01 | GET | `/auth/check-email/` | 이메일 중복 확인 | 없음 | P0 |
| AUTH-01 | GET | `/auth/check-nickname/` | 닉네임 중복 확인 | 없음 | P0 |
| AUTH-01 | GET | `/regions/` | 시·군·구 목록 | 없음 | P0 |
| AUTH-02 | POST | `/auth/login/` | 로그인 | 없음 | P0 |
| AUTH-02 | POST | `/auth/logout/` | 로그아웃 | 필요 | P0 |
| AUTH-02 | GET | `/users/me/` | 내 정보 | 필요 | P0 |
| ADM-01 | GET | `/ingredient-groups/` | 재료 그룹 목록·검색 | 없음 | P0 |
| ADM-01 | GET | `/ingredients/` | 표준 재료 자동완성 | 필요 | P0 |
| INV-01 | POST | `/captures/` | 캡처 업로드·인식 | 필요 | P0 |
| INV-01 | GET | `/captures/{capture_id}/` | 캡처·인식 결과 조회 | 필요 | P0 |
| INV-01 | POST | `/captures/{capture_id}/retry/` | 인식 재시도 | 필요 | P0 |
| INV-02 | POST | `/captures/{capture_id}/confirm/` | 인식 결과 확정·재고 저장 | 필요 | P0 |
| INV-03 | POST | `/inventory-items/` | 재료 직접 추가 (1~20건) | 필요 | P0 |
| INV-04 | GET | `/inventory-items/` | 냉장고 (재고 목록) | 필요 | P0 |
| INV-05 | GET | `/inventory-items/{item_id}/` | 재고 상세·이력 | 필요 | P0 |
| INV-05 | PATCH | `/inventory-items/{item_id}/` | 개봉·남은 양·소비기한 수정 | 필요 | P0 |
| INV-05·09 | POST | `/inventory-items/{item_id}/move/` | 보관 위치 변경 (P0: 통째로, P1: 일부 소분) | 필요 | P0 |
| INV-06 | POST | `/inventory-items/{item_id}/use-up/` | 다 씀 | 필요 | P0 |
| INV-06 | POST | `/inventory-items/{item_id}/discard/` | 버림 | 필요 | P0 |
| REC-01 | POST | `/recommendations/` | RAG 추천 요청 (REC-02·06 공용) | 필요 | P0 |
| REC-01 | POST | `/recommendations/impressions/{impression_id}/click/` | 추천 클릭 기록 | 필요 | P0 |
| REC-03 | GET | `/recipes/{recipe_id}/` | 레시피 상세 | 선택 | P0 |
| REC-05 | GET | `/recipes/{recipe_id}/completion-preview/` | 완료 확인 화면 데이터 | 필요 | P0 |
| REC-05 | POST | `/recipe-completions/` | 요리 완료·재고 차감 | 필요 | P0 |
| REC-07 | GET | `/guest/recipes/` | 비회원 재료로 레시피 보기 | 없음 | P0 |
| AUTH-03 | PATCH | `/users/me/` | 프로필 수정 | 필요 | P1 |
| AUTH-03 | POST | `/users/me/password/` | 비밀번호 변경 | 필요 | P1 |
| AUTH-04 | POST | `/users/me/withdraw/` | 회원 탈퇴 | 필요 | P1 |
| AUTH-05 | GET | `/users/{user_id}/` | 사용자 프로필 | 필요 | P1 |
| AUTH-05 | GET | `/users/{user_id}/posts/` | 사용자 게시글 (피드 / 나눔) | 필요 | P1 |
| 공통 | POST | `/uploads/images/` | 이미지 업로드 | 필요 | P1 |
| INV-07 | POST | `/inventory-events/{event_id}/revert/` | 재고 처리 취소 | 필요 | P1 |
| INV-07 | POST | `/recipe-completions/{completion_id}/revert/` | 요리 완료 취소 | 필요 | P1 |
| INV-08 | POST | `/inventory-items/{item_id}/check/` | "아직 있나요?" 응답 | 필요 | P1 |
| REC-02 | GET | `/welcome-card/` | 오늘의 냉장고 카드 표시 여부·재고 상태 | 필요 | P1 |
| REC-02 | POST | `/recommendations/{request_id}/next/` | 다음 순위 추천 보기 | 필요 | P1 |
| REC-02 | POST | `/recommendations/{request_id}/dismiss/` | 오늘은 그만 보기 | 필요 | P1 |
| REC-04 | GET | `/recipes/` | 레시피 검색 | 필요 | P1 |
| RPT-01 | GET | `/reports/daily/` | 오늘의 변화 | 필요 | P1 |
| RPT-02 | GET | `/reports/weekly/` | 주간 리포트 | 필요 | P1 |
| RPT-03 | GET | `/reports/monthly/` | 월간 가계부 | 필요 | P1 |
| SCR-02 | GET | `/scores/weekly/` | 점수 게이지·요일별 추이 | 필요 | P1 |
| SCR-02 | GET | `/users/me/score-events/` | 점수 내역 | 필요 | P1 |
| SCR-03 | GET | `/badges/` | 뱃지 목록 (획득 여부 포함) | 필요 | P1 |
| COM-01 | GET | `/posts/feed/` | 피드 목록 | 필요 | P1 |
| COM-02 | POST | `/posts/feed/brag/` | 자랑 글 작성 | 필요 | P1 |
| COM-03 | POST | `/posts/feed/recipe/` | 레시피 공유 글 작성 | 필요 | P1 |
| COM-04 | GET | `/posts/{post_id}/` | 게시글 상세 | 필요 | P1 |
| COM-02·03·06 | PATCH | `/posts/{post_id}/` | 게시글 수정 | 필요 | P1 |
| COM-02·03·06 | DELETE | `/posts/{post_id}/` | 게시글 삭제 | 필요 | P1 |
| COM-05 | GET | `/posts/share/` | 나눔 게시판 목록 | 필요 | P1 |
| COM-06 | POST | `/posts/share/` | 나눔 글 작성 | 필요 | P1 |
| COM-06 | POST | `/posts/{post_id}/trade-status/` | 거래 상태 변경 | 필요 | P1 |
| COM-07 | GET | `/posts/{post_id}/comments/` | 댓글 목록 | 필요 | P1 |
| COM-07 | POST | `/posts/{post_id}/comments/` | 댓글·답글 작성 | 필요 | P1 |
| COM-07 | PATCH | `/comments/{comment_id}/` | 댓글 수정 | 필요 | P1 |
| COM-07 | DELETE | `/comments/{comment_id}/` | 댓글 삭제 | 필요 | P1 |
| COM-08 | POST | `/posts/{post_id}/reaction/` | 좋아요·관심 토글 | 필요 | P1 |
| COM-09 | POST | `/users/{user_id}/follow/` | 팔로우 토글 | 필요 | P1 |
| COM-09 | GET | `/users/{user_id}/followers/` | 팔로워 목록 | 필요 | P1 |
| COM-09 | GET | `/users/{user_id}/followings/` | 팔로잉 목록 | 필요 | P1 |
| NOTI-02 | GET | `/notifications/unread-count/` | 안 읽은 알림 수 (폴링) | 필요 | P1 |
| NOTI-02 | GET | `/notifications/` | 알림 목록 | 필요 | P1 |
| NOTI-02 | POST | `/notifications/{notification_id}/read/` | 알림 읽음 | 필요 | P1 |
| NOTI-02 | POST | `/notifications/read-all/` | 모두 읽음 | 필요 | P1 |

> NOTI-01, BAT-01~03, ADM-02~04는 API 없이 서버 내부 처리·관리 명령·Django Admin으로 동작합니다. ([4장](#4-관리-명령배치) 참고)

---

## 2. P0 상세

### 2.1 회원 (AUTH)

#### `POST /auth/signup/`: 회원가입 (AUTH-01)

**Request**

```json
{
  "email": "jongyun@example.com",
  "password": "fridge1234!",
  "password_confirm": "fridge1234!",
  "nickname": "냉장고지킴이",
  "region_code": "30200",
  "household_size": 1,
  "preferred_cuisines": ["국&찌개", "반찬"]
}
```

| 필드 | 필수 | 규칙 |
| :--- | :---: | --- |
| email | O | 이메일 형식, 중복 불가 |
| password, password_confirm | O | Django 비밀번호 검증, 두 값 일치 |
| nickname | O | 2~20자, 중복 불가 |
| region_code | | `/regions/`의 코드 |
| household_size | | 1~10 |
| preferred_cuisines | | `밥` / `국&찌개` / `반찬` / `일품` / `후식` 중 다중 (공공 레시피 요리 종류와 같은 값) |

**Response `201`**

```json
{
  "user": {
    "id": 12,
    "email": "jongyun@example.com",
    "nickname": "냉장고지킴이",
    "profile_image_url": null,
    "region": { "region_code": "30200", "sido_name": "대전광역시", "sigungu_name": "유성구" }
  },
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
}
```

- 가입 즉시 로그인 상태가 됩니다.
- 비회원 선택 재료 옮기기는 서버가 따로 처리하지 않습니다. 프론트가 임시 저장 값이 있으면 가입 직후 안내를 띄우고 `POST /inventory-items/`로 저장합니다.
- **Errors**: `400 validation_error` (이메일·닉네임 중복, 비밀번호 규칙·불일치)

#### `GET /auth/check-email/?email=` · `GET /auth/check-nickname/?nickname=`: 중복 확인 (AUTH-01)

- 입력칸에서 포커스가 빠질 때 호출합니다.

**Response `200`**

```json
{ "available": false, "message": "이미 사용 중인 닉네임이에요." }
```

#### `GET /regions/`: 시·군·구 목록 (AUTH-01)

- 전체(약 250개)를 시·도별로 묶어서 한 번에 응답합니다.

**Response `200`**

```json
{
  "results": [
    {
      "sido_name": "대전광역시",
      "sigungu": [
        { "region_code": "30200", "sigungu_name": "유성구" },
        { "region_code": "30170", "sigungu_name": "서구" }
      ]
    }
  ]
}
```

#### `POST /auth/login/`: 로그인 (AUTH-02)

**Request**

```json
{ "email": "jongyun@example.com", "password": "fridge1234!" }
```

**Response `200`**: 회원가입 응답과 같은 형식 (`user`, `token`)

- **Errors**: `401 invalid_credentials` ("이메일 또는 비밀번호를 확인해 주세요")

#### `POST /auth/logout/`: 로그아웃 (AUTH-02)

- 본문 없음, 서버의 토큰을 삭제합니다. → **Response `204`**

#### `GET /users/me/`: 내 정보 (AUTH-02)

**Response `200`**

```json
{
  "id": 12,
  "email": "jongyun@example.com",
  "nickname": "냉장고지킴이",
  "profile_image_url": null,
  "bio": null,
  "household_size": 1,
  "preferred_cuisines": ["국&찌개", "반찬"],
  "region": { "region_code": "30200", "sido_name": "대전광역시", "sigungu_name": "유성구" },
  "is_public": true,
  "date_joined": "2026-11-27T10:12:00+09:00"
}
```

---

### 2.2 기준 데이터

#### `GET /ingredient-groups/`: 재료 그룹 목록·검색 (REC-07, COM-03)

- **인증**: 없음 (시작 화면 재료 칩에서 사용)
- **Query**: `q` (재료명 부분 일치), `featured=true` (시작 화면 기본 칩 20개 안팎만)

**Response `200`**

```json
{
  "results": [
    { "group_id": 3, "group_name": "계란", "category": "유제품·계란", "icon": "egg" },
    { "group_id": 7, "group_name": "대파", "category": "채소", "icon": "green_onion" }
  ]
}
```

- `icon`: 재료 그림 키 (`ingredient_group.icon`), 없으면 `null` → 프론트는 분류 기본 그림 사용

#### `GET /ingredients/`: 표준 재료 자동완성 (INV-02, INV-03)

- **Query**: `q` (재료명 부분 일치) 또는 `group_id` (그룹의 표준 재료 전체, 가입 직후 재료 넣기에서 사용), 둘 중 하나 필수

**Response `200`**

```json
{
  "results": [
    {
      "ingredient_id": 21,
      "ingredient_name": "저지방우유",
      "group": { "group_id": 5, "group_name": "우유", "icon": "milk" },
      "default_storage": "fridge",
      "available_storages": ["fridge"],
      "quantity_mode": "amount",
      "default_unit": "ml"
    }
  ]
}
```

- `available_storages`: 일수가 NULL이 아닌 보관 위치만 (예: 계란은 냉동 제외), 보관 위치 선택칸과 드래그에서 사용

---

### 2.3 재고 (INV)

#### `POST /captures/`: 캡처 업로드·인식 (INV-01)

- **Content-Type**: `multipart/form-data`, `image` (jpg·png·webp, 10MB 이하)
- **처리**: 업로드부터 비전 LLM 결과까지 한 요청에서 처리 (동기, 서버 시간 제한 20초), 화면은 응답이 올 때까지 "인식 중" 표시

**Response `201`** (인식 성공)

```json
{
  "capture_id": 88,
  "status": "recognized",
  "image_url": "/media/captures/88.jpg",
  "platform": "coupang",
  "purchase_date": "2026-11-26",
  "order_total_amount": 23400,
  "order_discount_amount": 2000,
  "delivery_fee": 0,
  "items": [
    {
      "capture_item_id": 501,
      "raw_product_name": "곰곰 무항생제 대란 30구",
      "raw_quantity_text": "30구",
      "is_food": true,
      "predicted_price": 8990,
      "predicted_quantity": 30,
      "predicted_unit": "개",
      "predicted_ingredient": { "ingredient_id": 3, "ingredient_name": "계란", "default_storage": "fridge", "available_storages": ["fridge", "room"] }
    },
    {
      "capture_item_id": 502,
      "raw_product_name": "탐사 키친타월 6롤",
      "raw_quantity_text": "6롤",
      "is_food": false,
      "predicted_price": 6900,
      "predicted_quantity": null,
      "predicted_unit": null,
      "predicted_ingredient": null
    }
  ],
  "warnings": []
}
```

- `predicted_ingredient`가 `null`이고 `is_food = true`면 확인 화면에서 "재료를 선택해 주세요"
- `is_food = false`는 확인 화면에서 기본 제외 상태
- 품목을 하나도 찾지 못하면 `items = []`, `warnings = ["no_items_found"]` → 화면에서 직접 추가 버튼

**Response `201`** (인식 실패, 이미지는 저장됨)

```json
{ "capture_id": 89, "status": "failed", "error_message": "인식 시간이 초과됐어요.", "items": [] }
```

- **Errors**: `400 invalid_file`

#### `GET /captures/{capture_id}/`: 캡처 조회 (INV-01, INV-02)

- 새로고침해도 확인 화면을 다시 그릴 수 있도록 `POST /captures/`와 같은 형식으로 응답합니다.
- 확정된 캡처는 `status = "confirmed"`, 품목에 `confirmed_*` 값을 포함합니다.

#### `POST /captures/{capture_id}/retry/`: 인식 재시도 (INV-01)

- `status = "failed"`인 캡처만 가능하며, 응답은 `POST /captures/`와 같습니다.
- **Errors**: `409 conflict` (실패 상태가 아님)

#### `POST /captures/{capture_id}/confirm/`: 인식 결과 확정·재고 저장 (INV-02)

- 확인 화면에서 고친 내용은 프론트가 들고 있다가 "저장"할 때 한 번에 보냅니다. 서버는 한 트랜잭션으로 처리합니다.

**Request**

```json
{
  "platform": "coupang",
  "purchase_date": "2026-11-26",
  "order_discount_amount": 2000,
  "delivery_fee": 0,
  "items": [
    { "capture_item_id": 501, "is_excluded": false, "ingredient_id": 3, "quantity": 30, "unit": "개", "price": 8990, "storage": "fridge" },
    { "capture_item_id": 502, "is_excluded": true }
  ]
}
```

| 필드 | 필수 | 규칙 |
| :--- | :---: | --- |
| purchase_date | O | 오늘 또는 그 이전 날짜 (미래 날짜 불가) |
| items[] | O | 캡처의 모든 capture_item을 빠짐없이 포함 |
| items[].is_excluded | O | `true`면 나머지 필드 생략 가능 |
| items[].ingredient_id | 제외 안 함이면 O | 표준 재료 |
| items[].quantity, unit | count·amount 재료면 O | presence 재료는 생략 |
| items[].price | | 미입력 시 `null` |
| items[].storage | | 생략 시 재료의 default_storage, available_storages 안에서만 |

**Response `201`**

```json
{
  "capture_id": 88,
  "status": "confirmed",
  "created_items": [
    { "item_id": 1201, "ingredient_name": "계란", "storage": "fridge", "expiry": { "expected_date": "2026-12-26", "days_left": 29, "status": "ok", "source": "auto" } }
  ],
  "most_urgent": { "item_id": 1203, "ingredient_name": "두부", "days_left": 4 },
  "warnings": ["amount_mismatch"],
  "badges_earned": [{ "code": "first_capture", "name": "첫 캡처 등록", "icon": "badge_first_capture" }]
}
```

- `warnings`: `amount_mismatch` (품목 합계 - 할인 + 배송비 ≠ 총 결제 금액, 저장은 됨)
- **Errors**: `400 validation_error` (재료 미선택 품목, 보관 위치 불가), `409 conflict` (이미 확정·실패 상태)

#### `POST /inventory-items/`: 재료 직접 추가 (INV-03)

- 냉장고의 "재료 넣기"와 가입 직후 고른 재료 넣기에서 사용합니다.

**Request** (1~20건)

```json
{
  "items": [
    { "ingredient_id": 7, "quantity": 1, "unit": "개", "purchase_date": "2026-11-27", "storage": "fridge", "price": 2490 },
    { "ingredient_id": 40, "purchase_date": "2026-11-27" }
  ]
}
```

- `purchase_date` 생략 시 오늘, `storage` 생략 시 기본 보관 위치, presence 재료는 수량 생략
- 한 건이라도 오류면 전체를 저장하지 않습니다. (`fields`에 `items.1.quantity` 형식으로 위치 표시)

**Response `201`**: `{ "created_items": [ ...냉장고 목록의 재고 형식... ] }`

#### `GET /inventory-items/`: 냉장고 (INV-04)

- active 재고를 **구매 건(lot) 단위로 평평하게** 응답합니다. 칸별 묶기·같은 재료 묶기·정렬은 프론트가 합니다.
- 요약 숫자는 화면마다 같아야 하므로 서버가 `summary`로 함께 줍니다.
- **Query**: `storage` (`fridge` / `freezer` / `room`, 생략 시 전체)

**Response `200`**

```json
{
  "summary": { "total_count": 14, "expiring_count": 3, "check_needed_count": 1 },
  "results": [
    {
      "item_id": 1203,
      "ingredient": { "ingredient_id": 25, "ingredient_name": "두부", "group_id": 25, "group_name": "두부", "icon": "tofu", "quantity_mode": "count" },
      "storage": "fridge",
      "zone": "fridge_shelf",
      "purchase_date": "2026-11-24",
      "purchase_price": 1800,
      "is_opened": false,
      "quantity": { "mode": "count", "remaining": 1, "initial": 1, "unit": "개", "level": null, "text": "1개" },
      "expiry": { "expected_date": "2026-11-28", "days_left": 1, "status": "expiring", "source": "auto" },
      "created_at": "2026-11-24T19:02:00+09:00"
    }
  ]
}
```

- 프론트 묶기 규칙: 같은 `ingredient_id` + 같은 `zone`이면 그림 하나로 묶고, 묶음의 소비기한 배지는 가장 빠른 건 기준
- 임박 목록(냉장고 옆, 홈 요약): `expiry.status`가 `expiring`·`expired`·`check_needed`인 건을 `days_left` 오름차순

#### `GET /inventory-items/{item_id}/`: 재고 상세 (INV-05)

**Response `200`**: 냉장고 목록의 재고 형식에 아래 필드를 더해 응답

```json
{
  "remaining_value": 1800,
  "opened_at": null,
  "available_storages": ["fridge", "freezer"],
  "has_opened_days": true,
  "parent_item_id": null,
  "share_post_id": null,
  "events": [
    { "event_id": 9001, "event_type": "created", "quantity_delta": 1, "value_delta": null, "created_at": "2026-11-24T19:02:00+09:00", "revertible": false }
  ]
}
```

- `parent_item_id`: 소분으로 나뉜 건이면 원래 건의 ID
- `share_post_id`: 연결된 나눔 글이 있으면 ID ("나눔하기" 대신 "나눔 글 보기")
- `revertible`: 취소 가능한 이벤트인지 (INV-07)

#### `PATCH /inventory-items/{item_id}/`: 개봉·남은 양·소비기한 수정 (INV-05)

**Request** (한 번에 한 종류만)

```json
{ "remaining_level": "half" }
```

| 필드 | 생성 이벤트 | 규칙 |
| :--- | --- | --- |
| `is_opened: true` | opened | 개봉 개념이 없는 재료는 불가, 소비기한 = MIN(현재, 오늘 + opened_days) |
| `remaining_quantity` | adjusted | count 재료, 0 초과 initial 이하 (0은 "다 씀" 사용 안내) |
| `remaining_level` | adjusted | amount 재료, `many` / `half` / `little` → 처음 양의 80% / 50% / 20%로 저장, 이미 그 단계면 변경 없음 |
| `expected_expiry_date` | (이벤트 없음, expiry_source = manual) | 오늘 이후 날짜 |

- 남은 양은 **늘리는 것도 가능**합니다. (처음 양까지) 늘어난 만큼은 `value_delta`를 마이너스로 기록해 앞선 소진 기록을 바로잡습니다.
- 보관 위치는 이 API가 아니라 `POST .../move/`로 바꿉니다.

**Response `200`**: 재고 상세와 같은 형식

- **Errors**: `400 validation_error` (두 종류 이상 동시 수정, 처음 양 초과), `409 conflict` (active가 아님)

#### `POST /inventory-items/{item_id}/move/`: 보관 위치 변경·소분 (INV-05, INV-09)

**Request**

```json
{ "storage": "freezer", "quantity": 200 }
```

| 필드 | 필수 | 규칙 |
| :--- | :---: | --- |
| storage | O | available_storages 안에서만, 현재와 다른 값 |
| quantity | | 비우거나 남은 양 전부면 **통째로 이동** (P0), 일부면 **소분** (P1), presence 재료는 통째로만 |

- **소비기한 계산**: 냉동으로 옮기면 오늘 + 냉동 일수, 그 외에는 MIN(현재 소비기한, 오늘 + 새 보관 위치 일수), manual이면 유지
- **통째로 이동**: storage 변경, 위 규칙으로 소비기한 재계산, `storage_changed` 이벤트
- **소분**: 원래 건의 수량·구매 가격을 줄이고, 옮긴 만큼 새 재고를 만듦
  - 새 건 가격 = 원래 가격 × (옮긴 수량 / 원래 처음 수량), 두 건의 가격 합은 원래 가격과 같음
  - 새 건은 구매일이 같고, 소비기한은 위 규칙으로 계산, `parent_item_id`에 원래 건 연결
  - 두 건 모두에 `split` 이벤트 기록, 다시 같은 칸으로 옮겨도 합치지 않음
- 보관 위치 변경·소분은 처리 취소(INV-07) 대상이 아닙니다.

**Response `200`**

```json
{
  "item": { "item_id": 1188, "storage": "fridge", "zone": "fridge_shelf", "quantity": { "mode": "amount", "remaining": 300, "initial": 300, "unit": "g", "level": "many", "text": "많음" }, "...": "..." },
  "new_item": { "item_id": 1250, "storage": "freezer", "zone": "freezer", "parent_item_id": 1188, "expiry": { "expected_date": "2026-12-27", "days_left": 30, "status": "ok", "source": "auto" }, "...": "..." }
}
```

- 통째로 이동하면 `new_item`은 `null`
- 임박 경고("상하지 않았는지 확인해 주세요")는 프론트가 `expiry.status`로 판단해 확인 창에 표시합니다.
- **Errors**: `400 validation_error` (쓸 수 없는 보관 위치, 남은 양 초과, presence 재료 소분, 기한이 지난 재고를 냉동으로 이동), `409 conflict` (active가 아님)

#### `POST /inventory-items/{item_id}/use-up/` · `POST /inventory-items/{item_id}/discard/`: 다 씀·버림 (INV-06)

- 본문 없음

**Response `200`**

```json
{
  "item_id": 1203,
  "status": "discarded",
  "event_id": 9050,
  "value_delta": 1800,
  "message": "1,800원어치 폐기",
  "score": { "delta": -5, "reason": "두부 1,800원어치 폐기", "current_score": 61, "capped": false },
  "revertible_until": "2026-11-28T10:30:00+09:00"
}
```

- 토스트의 취소 버튼은 `revertible_until`까지 `POST /inventory-events/{event_id}/revert/` (P1)를 호출합니다.
- **Errors**: `409 conflict` (이미 처리된 재고)

---

### 2.4 레시피·추천 (REC)

#### `POST /recommendations/`: RAG 추천 요청 (REC-01, REC-02, REC-06)

- 요청·후보·LLM 응답·노출을 기록하는 동작이라 `POST`를 씁니다.

**Request**

```json
{ "trigger": "home" }
```

| trigger | 용도 | 비고 |
| :--- | --- | --- |
| `home` | 레시피 화면·홈 추천 | 같은 날 같은 재고 조합이면 캐시 사용 |
| `refresh` | 다른 추천 보기 (새로고침) | 캐시 사용 안 함, 이전 노출 레시피 후순위 |
| `welcome` | 오늘의 냉장고 카드 (P1) | 1개만 노출, 다음 순위는 `/next/` |
| `ingredient` | 특정 재료로 추천 (P1) | `item_id` 필수 |

- `meal_slot`은 서버가 요청 시각으로 계산합니다.
- **처리 시간**: 동기 처리, 캐시 적중 1초 이내·미적중 수 초 (LLM 시간 제한 15초, 넘으면 검색 상위 결과로 대체), 화면은 카드 자리만 먼저 표시

**Response `200`**

```json
{
  "request_id": "6f1c2a4e-9b1d-4c1e-8f0a-2d3b4c5d6e7f",
  "status": "success",
  "cache_hit": false,
  "meal_slot": "lunch",
  "basis": "expiring",
  "recipes": [
    {
      "impression_id": 7001,
      "rank": 1,
      "recipe": {
        "recipe_id": 345,
        "recipe_name": "두부조림",
        "image_url": "https://www.foodsafetykorea.go.kr/uploadimg/cook/10_00345_1.png",
        "dish_type": "반찬",
        "source": "public"
      },
      "reason": "내일까지인 두부와 대파를 한 번에 쓸 수 있어요.",
      "used_items": [{ "item_id": 1203, "ingredient_name": "두부", "days_left": 1 }],
      "expiring_used_cnt": 2,
      "owned_cnt": 4,
      "total_cnt": 5,
      "substitutes": [{ "missing": "청양고추", "suggestion": "고춧가루로 대체할 수 있어요." }]
    }
  ]
}
```

- `status`: `success` / `fallback` (LLM 실패·검증 실패 → 검색 상위 결과, `reason`은 기본 문구)
- `basis`: `expiring` (임박 재료 기준) / `owned` (임박 재료 없음) / `empty` (재고 없음 → 시간대 공공 레시피, 화면에 등록 안내)
- `owned_cnt`, `total_cnt`: 양념 제외 재료 기준 ("재료 5개 중 4개 보유")
- **Errors**: `502 external_api_error` (검색까지 실패 → "추천을 불러오지 못했어요" + 검색 버튼), `400 validation_error` (`ingredient`인데 `item_id` 없음)

#### `POST /recommendations/impressions/{impression_id}/click/`: 추천 클릭 기록 (REC-03)

- 추천 카드에서 상세로 이동할 때 프론트가 따로 호출합니다. (`is_clicked = TRUE`, 상세 조회는 데이터를 바꾸지 않음)
- **Response `204`**

#### `GET /recipes/{recipe_id}/`: 레시피 상세 (REC-03)

- **인증**: 선택 (비회원 열람 가능)
- **Query**
  - `impression_id` (선택): 추천에서 들어온 경우 → 응답에 추천 이유 포함
  - `groups` (비회원만): 시작 화면에서 고른 재료 그룹 ID, 쉼표 구분 (예: `groups=3,7,12`)

**Response `200`**

```json
{
  "recipe_id": 345,
  "recipe_name": "두부조림",
  "source": "public",
  "author": null,
  "feed_post_id": null,
  "dish_type": "반찬",
  "cooking_method": "조리기",
  "servings": 1,
  "image_url": "https://www.foodsafetykorea.go.kr/uploadimg/cook/10_00345_1.png",
  "tip": "간장은 저염 간장을 사용하면 나트륨을 줄일 수 있어요.",
  "is_active": true,
  "ingredients": [
    {
      "recipe_ingredient_id": 9120,
      "section": "주재료",
      "ingredient_name": "두부",
      "amount_text": "100g(1/3모)",
      "group_id": 25,
      "is_seasoning": false,
      "is_optional": false,
      "owned_status": "expiring"
    }
  ],
  "steps": [{ "order": 1, "text": "두부는 1cm 두께로 썰어 소금을 뿌려 둔다.", "image_url": "https://..." }],
  "recommendation": { "impression_id": 7001, "reason": "내일까지인 두부와 대파를 한 번에 쓸 수 있어요." },
  "owned_cnt": 4,
  "total_cnt": 5,
  "can_complete": true
}
```

- `owned_status`: 회원은 `owned` / `expiring` / `missing`, 비회원은 `owned` / `missing` (고른 그룹 기준), 그룹 매칭이 안 된 재료는 `unknown`
- `can_complete`: 비회원이면 `false` → "요리 완료"를 누르면 가입 안내
- 비활성 레시피는 `is_active = false`로 내용과 함께 응답 (화면에서 "삭제된 레시피예요", 완료 기록에서 들어온 경우 내용 표시)
- **Errors**: `404 not_found`

#### `GET /recipes/{recipe_id}/completion-preview/`: 완료 확인 화면 데이터 (REC-05)

- "요리 완료"를 누를 때 호출합니다. (누르는 시점의 재고 기준)
- **Query**: `impression_id` (선택, 추천의 used_items를 기본 선택)

**Response `200`**

```json
{
  "recipe_id": 345,
  "recipe_name": "두부조림",
  "impression_id": 7001,
  "ingredients": [
    {
      "recipe_ingredient_id": 9120,
      "ingredient_name": "두부",
      "amount_text": "100g(1/3모)",
      "quantity_mode": "count",
      "default_item_id": 1203,
      "default_selected": true,
      "candidates": [
        {
          "item_id": 1203,
          "ingredient_name": "두부",
          "purchase_date": "2026-11-24",
          "quantity": { "mode": "count", "remaining": 1, "initial": 1, "unit": "개", "level": null, "text": "1개" },
          "expiry": { "expected_date": "2026-11-28", "days_left": 1, "status": "expiring", "source": "auto" }
        }
      ]
    }
  ]
}
```

- 보유한 재료(같은 그룹 active 재고가 있는 재료)만 포함하고, `candidates`는 소비기한 빠른 순입니다.
- "재료 추가"(레시피에 없는 재료)는 `GET /inventory-items/` 목록에서 고릅니다.

#### `POST /recipe-completions/`: 요리 완료·재고 차감 (REC-05)

**Request**

```json
{
  "recipe_id": 345,
  "impression_id": 7001,
  "servings": 1,
  "usages": [
    { "item_id": 1203, "usage_level": "count", "count": 1 },
    { "item_id": 1188, "usage_level": "half" }
  ],
  "confirm_without_inventory": false
}
```

| 필드 | 규칙 |
| :--- | --- |
| usages[].usage_level | amount 재료: `all` / `half` / `little` / `none` (남은 양의 100% / 50% / 25% / 0%), count 재료: `count` + `count`(1 이상 남은 개수 이하), presence 재료: 생략 또는 `none` |
| usages[].item_id | 내 active 재고 (레시피에 없는 재료도 가능), 같은 재고 중복 불가 |
| confirm_without_inventory | `usages`가 비었거나 모두 `none`이면 `true`로 보내야 완료 기록만 저장 (아니면 `400`) |

**Response `201`**

```json
{
  "completion_id": 520,
  "recipe_id": 345,
  "used_value": 4800,
  "expiring_used_cnt": 2,
  "message": "임박 재료 2개 · 4,800원어치 소진",
  "consumed": [
    { "event_id": 9060, "item_id": 1203, "ingredient_name": "두부", "usage_level": "count", "quantity_delta": -1, "value_delta": 1800, "item_status": "used_up" }
  ],
  "score": { "delta": 8, "reason": "임박 재료 2개 소진", "current_score": 72, "capped": false },
  "revertible_until": "2026-11-28T12:40:00+09:00"
}
```

- 화면: 결과 메시지 + "피드에 자랑하기"(`completion_id`로 COM-02 연결) + 취소 버튼 (`POST /recipe-completions/{completion_id}/revert/`, P1)
- **Errors**: `400 validation_error` (사용량 오류, 보유 재료 없이 확인 안 함), `404 not_found` (다른 사람 재고), `409 conflict` (이미 처리된 재고)

#### `GET /guest/recipes/`: 비회원 재료로 레시피 보기 (REC-07)

- **인증**: 없음, IP 기준 분당 30회 제한 (개발하면서 조정)
- **Query**: `groups` (필수, 재료 그룹 ID 1~10개, 쉼표 구분), `page`
- **처리**: 키워드 매칭만 사용 (LLM·임베딩 없음), 기록 저장 없음, 한 페이지 12개

**Response `200`**

```json
{
  "results": [
    {
      "recipe_id": 345,
      "recipe_name": "두부조림",
      "image_url": "https://www.foodsafetykorea.go.kr/uploadimg/cook/10_00345_1.png",
      "dish_type": "반찬",
      "matched_cnt": 3,
      "missing_cnt": 2,
      "matched_groups": ["두부", "대파", "간장"]
    }
  ],
  "count": 41,
  "page": 1,
  "next": 2,
  "has_next": true
}
```

- 정렬: `matched_cnt` 내림차순 → `missing_cnt`(양념 제외) 오름차순
- 결과 없음: `results = []` (화면에서 "재료를 하나 빼 보세요")
- **Errors**: `400 validation_error` (groups 없음·11개 이상), `429 too_many_requests`

---

### 2.5 점수 피드백 (SCR-01)

- 별도 API 없이, 점수가 바뀌는 API의 응답에 [`score` 객체](#07-공통-객체)를 포함합니다.
- 점수 규칙별 값과 공식(임박 가중치, 폐기 감점 단위, 하루 상한)은 데이터 준비 단계에서 정해 `score_rule` 시드로 적재합니다.

| 점수가 바뀌는 API | 적용 규칙 |
| :--- | --- |
| `POST /inventory-items/{id}/use-up/` | expiring_used 또는 used_up |
| `POST /inventory-items/{id}/discard/` | discarded |
| `POST /recipe-completions/` | 임박 재료별 expiring_used, 임박이 아닌 재료를 다 쓰면(남은 수량 0) used_up |
| `POST /inventory-items/{id}/check/` (P1) | 다 먹었어요·버렸어요 응답 시 INV-06과 같음 |
| `POST /posts/{id}/trade-status/` (P1) | done 변경 시 shared_done |
| `POST /inventory-events/{id}/revert/`, `POST /recipe-completions/{id}/revert/` (P1) | 원래 점수의 반대 값 |

- 남은 양 수정(`PATCH`), 보관 위치 변경·소분(`move`)에는 점수가 없습니다.
- 프론트는 `score`가 있으면 토스트("+8점 · 임박 재료 2개 소진")와 게이지 애니메이션을 띄우고, 게이지 값은 `current_score`로 갱신합니다.

---

## 3. P1 요약

> 경로·주요 파라미터·응답 필드만 정의합니다. 공통 규칙(인증, 에러, 페이지, 공통 객체)은 0장을 따르며, 요청·응답 예시는 구현하면서 채웁니다.

### 3.1 회원·프로필 (AUTH-03~05)

| API | 요청 | 응답 |
| :--- | --- | --- |
| `PATCH /users/me/` | nickname, profile_image_path(업로드 API 결과), bio, household_size, preferred_cuisines, region_code, is_public 중 일부 | 내 정보 |
| `POST /users/me/password/` | current_password, new_password, new_password_confirm | `204` / `400` (현재 비밀번호 불일치) |
| `POST /users/me/withdraw/` | password | `204`, 토큰 삭제 |
| `GET /users/{user_id}/` | — | id, nickname, profile_image_url, bio, region, is_public, is_withdrawn, this_week_score(비공개·비팔로워면 null), badges[{code, name, icon, count}], follower_cnt, following_cnt, is_following, is_me |
| `GET /users/{user_id}/posts/` | board=`feed`/`share`, cursor | 피드 카드 또는 나눔 목록 항목 (비공개·비팔로워면 feed는 빈 목록) |

### 3.2 이미지 업로드

| API | 요청 | 응답 |
| :--- | --- | --- |
| `POST /uploads/images/` | multipart: image(jpg·png·webp), purpose=`post`/`profile`/`recipe_step` (profile 5MB, 나머지 10MB 이하) | image_path, url |

### 3.3 재고 (INV-07~09)

| API | 요청 | 응답 |
| :--- | --- | --- |
| `POST /inventory-events/{event_id}/revert/` | — | reverted_event_id, item(재고 상세), score / `409 revert_not_allowed` |
| `POST /recipe-completions/{completion_id}/revert/` | — | reverted_event_ids, score (완료의 consumed 이벤트 전체 취소) |
| `POST /inventory-items/{item_id}/check/` | response=`still_have`/`used_up`/`discarded` | item, next_check_date(still_have), score |
| `POST /inventory-items/{item_id}/move/` (소분) | storage, quantity(일부) | item, new_item (2.3 참고) |

- 드래그(INV-09) 확인 창: 묶인 재료의 구매 건 목록을 보여주고(소비기한 빠른 건 기본 체크), 건마다 "전부 / 일부(수량)"를 골라 체크한 건마다 `move`를 호출합니다. 냉장고 안 칸끼리 이동(선반 ↔ 채소칸 ↔ 도어)은 API를 호출하지 않습니다.

### 3.4 레시피·추천 (REC-02·04·06)

| API | 요청 | 응답 |
| :--- | --- | --- |
| `GET /welcome-card/` | — | show(표시 여부), meal_slot, expiring_cnt, expiring_names(최대 3), check_needed_cnt, this_week_score |
| `POST /recommendations/` (trigger=`welcome`) | — | 추천 응답과 같음, recipes는 1개 |
| `POST /recommendations/{request_id}/next/` | — | 다음 순위 추천 1개 (impression 생성, LLM 호출 없음) / 남은 후보 없으면 `409` |
| `POST /recommendations/{request_id}/dismiss/` | — | `204` (dismissed = TRUE) |
| `POST /recommendations/` (trigger=`ingredient`) | item_id | 추천 응답과 같음 / 후보 없으면 recipes = [] |
| `GET /recipes/` | q, dish_type, source=`all`/`public`/`user`, sort=`relevance`/`owned_ratio`, page | recipe_id, recipe_name, image_url, dish_type, source, owned_cnt, total_cnt |

- 오늘의 냉장고 카드 흐름: 홈 진입 → `GET /welcome-card/` → `show = true`면 재고 상태를 먼저 그리고 → `POST /recommendations/`(welcome)로 추천을 이어서 표시

### 3.5 분석·점수 (RPT, SCR-02·03)

| API | 요청 | 응답 |
| :--- | --- | --- |
| `GET /reports/daily/` | date (기본 오늘) | used_value, expiring_used_value, wasted_value, shared_value, score_delta (금액이 음수로 계산되면 0으로 응답) |
| `GET /reports/weekly/` | week_start (월요일, 기본 이번 주) | item_spend, order_discount, delivery_fee, used_value, wasted_value, shared_value, waste_rate, top_wasted[{ingredient_name, value}], prev_wasted_value, prev_item_spend, score{final_score, is_finalized, daily[{date, score}]} / 기록 없으면 has_data = false |
| `GET /reports/monthly/` | month (`YYYY-MM`, 기본 이번 달) | item_spend, order_discount, delivery_fee, net_spend, wasted_value, purchase_cnt, missing_price_cnt |
| `GET /scores/weekly/` | week_start (기본 이번 주) | current_score, gauge(0~100), is_full, daily[{date, score}], recent_events(5개) / 그 주 점수 이벤트가 없으면 current_score = 50(기본 점수)으로 응답 |
| `GET /users/me/score-events/` | week_start(선택), cursor | score_event_id, delta, reason, rule_code, created_at |
| `GET /badges/` | — | code, name, description, icon, badge_type, earned_count, last_earned_at (못 받은 뱃지는 earned_count = 0) |

### 3.6 커뮤니티 (COM-01~09)

| API | 요청 | 응답 |
| :--- | --- | --- |
| `GET /posts/feed/` | scope=`all`/`following`, type=`all`/`brag`/`recipe`, cursor | post_id, author{id, nickname, profile_image_url}, feed_type, thumbnail_url, content_preview, completion_badge{expiring_used_cnt, used_value}, recipe{recipe_id, recipe_name}, like_cnt, comment_cnt, is_liked, created_at |
| `POST /posts/feed/brag/` | content, image_paths(1~5), completion_id(선택, 최근 7일 내 내 완료) | 게시글 상세 |
| `POST /posts/feed/recipe/` | recipe_name, image_path, servings, dish_type, content, ingredients[{ingredient_name, amount_text, group_id}], steps[{text, image_path}] | 게시글 상세 (recipe_id 포함) |
| `GET /posts/{post_id}/` | — | 공통(post_id, board, author, content, images, reaction_cnt, is_reacted, comment_cnt, is_mine, created_at) + feed{feed_type, completion_badge, recipe} 또는 share{title, share_type, region, trade_status, item} / 삭제 글 `404` |
| `PATCH /posts/{post_id}/` | 작성 필드 중 바꿀 값 (자랑 글의 completion_id는 변경 불가) | 게시글 상세 / `403` |
| `DELETE /posts/{post_id}/` | — | `204` (소프트 삭제, 레시피 글은 레시피 비활성화) |
| `GET /posts/share/` | region_code(기본 내 지역), trade_status, share_type, cursor | post_id, title, thumbnail_url, region, trade_status, interest_cnt, comment_cnt, created_at / 지역 미설정이면 region_required = true와 전체 지역 목록 |
| `POST /posts/share/` | title, content, share_type=`give`/`exchange`, region_code, image_paths(0~5), item_id(선택) | 게시글 상세 / `409` (이미 다른 나눔 글에 연결된 재고) |
| `POST /posts/{post_id}/trade-status/` | trade_status=`open`/`reserved`/`done` | trade_status, item_status, score, badges_earned / `409` (done 이후 변경) |
| `GET /posts/{post_id}/comments/` | — (나누지 않고 전부) | comment_id, author, content, is_deleted, is_mine, created_at, replies[...] |
| `POST /posts/{post_id}/comments/` | content(1~500자), parent_id(선택, 최상위 댓글만) | 댓글 / `409` (삭제된 게시글) |
| `PATCH /comments/{comment_id}/` | content | 댓글 / `403` |
| `DELETE /comments/{comment_id}/` | — | `204` (is_deleted = TRUE) |
| `POST /posts/{post_id}/reaction/` | — (토글) | is_reacted, reaction_cnt |
| `POST /users/{user_id}/follow/` | — (토글) | is_following, follower_cnt / 자기 자신 `400` |
| `GET /users/{user_id}/followers/` · `/followings/` | cursor | id, nickname, profile_image_url, is_following |

- 토글 API는 응답의 현재 상태(`is_reacted`, `is_following`)로 화면을 맞추고, 프론트는 요청 중에 버튼을 잠깐 비활성화합니다.

### 3.7 알림 (NOTI-02)

| API | 요청 | 응답 |
| :--- | --- | --- |
| `GET /notifications/unread-count/` | — | unread_count (페이지 이동 시 + 30초마다 호출) |
| `GET /notifications/` | cursor (최근 30일) | notification_id, notif_type, message, actor{id, nickname, profile_image_url}, target{type, id, exists}, is_read, created_at |
| `POST /notifications/{notification_id}/read/` | — | `204` |
| `POST /notifications/read-all/` | — | `204` |

- 프론트는 `target.type`·`target.id`로 이동 경로를 정하고, `exists = false`면 "삭제된 콘텐츠예요"를 안내합니다.

---

## 4. 관리 명령·배치

API 없이 서버에서 실행하는 기능입니다. 명령 이름은 개발 환경 구성 때 확정합니다.

| 기능 ID | 실행 방식 | 명령 (예시) | 주기 |
| :--- | --- | --- | --- |
| ADM-01 | 관리 명령 + Django Admin | `python manage.py seed_reference` (시·군·구, 재료 그룹·표준 재료·그림 키, 상품명 매핑, 시작 화면 칩) | 최초 1회, 기준값 수정은 Admin |
| ADM-02 | 관리 명령 | `import_recipes` → `split_recipe_ingredients` → `embed_recipes` | 최초 1회, 이후 필요 시 |
| ADM-03 | Django Admin | 매칭 실패 재료 모아 보기, 일괄 그룹 연결 액션 | 수시 |
| ADM-04 | 데이터 마이그레이션 또는 관리 명령 + Django Admin | `seed_scoring` (점수 규칙·뱃지) | 최초 1회 |
| NOTI-01 | 서비스 내부 함수 | 댓글·반응·팔로우·거래 상태·뱃지 처리 안에서 호출 | 이벤트 발생 시 |
| BAT-01 | 스케줄 실행 | `notify_expiring` | 매일 09:00 |
| BAT-02 | 스케줄 실행 | `check_expired` | 매일 00:10 |
| BAT-03 | 스케줄 실행 | `finalize_week` | 매주 월요일 00:30 |

- 스케줄러(cron, django-crontab, APScheduler 등)는 배포 환경을 정할 때 결정합니다.
- 관리 명령과 배치는 두 번 실행해도 결과가 중복되지 않게 작성합니다. (이미 있으면 갱신, 알림 dedup_key, 확정 여부 확인)

---

## 5. 확장 시 변경 예정

| 항목 | 지금 (MVP) | 확장 시 |
| :--- | --- | --- |
| 인증 | DRF 토큰, 만료 없음, 회원 API 직접 구현 | 모바일·소셜 로그인 확장 시 dj-rest-auth(+ allauth) 또는 JWT로 전환, 주소·응답 모양은 유지 |
| 토큰 만료 | 없음 | 배포 전 "로그인 후 일정 기간(예: 14일) 뒤 만료" 추가 검토 |
| 캡처 인식 | 동기 처리 (20초 제한) | 느려지면 비동기(작업 큐 + 폴링)로 전환, 인식 로직은 서비스 함수로 분리해 둠 |
| 이미지 정리 | 쓰지 않은 업로드 이미지 남음 | 정리 배치 추가 |
