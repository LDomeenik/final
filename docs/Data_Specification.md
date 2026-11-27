# 데이터 명세서

```
본 프로젝트는 이미지 입력부터 재고·가격 관리, RAG 레시피 추천, 소비·폐기 기록, 점수, 커뮤니티까지의 흐름을
데이터 관점에서 일관되게 관리하기 위해 테이블을 9개 영역과 리포트 View로 나누어 설계하였습니다.

- 회원 데이터: 사용자(커스텀 User)와 활동 지역 기준값
- 기준 데이터: 표준 재료, 재료 그룹, 상품명 매핑 등 서비스 전체의 기준값
- 레시피 데이터: 공공 레시피 DB와 사용자 레시피, 레시피 재료, RAG 검색용 임베딩
- 입력 데이터: 캡처 이미지와 인식 결과(LLM 원본 / 사용자 확정본, 가격 포함)
- 재고 데이터: 사용자별 재고(구매 가격 포함)와 재고 변경 이력(금액 포함)
- 추천 데이터: RAG 추천 요청, 추천 노출, 레시피 완료 이력
- 커뮤니티 데이터: 게시글(피드·나눔), 이미지, 댓글, 반응, 팔로우
- 점수 데이터: 점수 규칙, 점수 이벤트, 주간 점수, 뱃지
- 알림 데이터: 서비스 내 알림
- 리포트 View: 오늘의 변화, 주간 리포트, 월간 가계부, 재료별 활용률

데이터베이스는 PostgreSQL(+ pgvector)을 사용하며, 사용자 테이블은 Django 커스텀 User 모델을 사용합니다.
확장 기능에서 사용할 테이블은 문서 마지막의 부록에 정리합니다.
```

> **확정 범위**: P0 테이블(회원, 기준 데이터, 레시피, 입력, 재고, 추천, 점수의 기본 구조)은 첫 모델 PR에서 확정합니다.
> 추천 로그의 JSONB 내용, 점수 규칙 값, 리포트 View, 인덱스, P1 테이블(커뮤니티·알림)은 구현하면서 조정하며, 바뀌면 같은 PR에서 이 문서를 함께 수정합니다.

**설계 원칙**

- **사용자는 처음부터 커스텀 User로 관리**
  - Django는 프로젝트 중간에 User 모델을 바꾸기 어려우므로 첫 마이그레이션 전에 커스텀 User(AbstractUser)를 설정
  - 이메일로 로그인하고, 화면에는 중복 불가 닉네임을 표시
  - 소셜 계정 정보는 User에 넣지 않고 확장 시 별도 테이블로 연결
- **재료는 2단계로 관리**
  - 표준 재료(ingredient): 소비기한 기준값 단위. 소비기한이나 기본 보관 위치가 다르면 다른 재료로 분리 (예: 우유 / 저지방우유 / 멸균우유)
  - 재료 그룹(ingredient_group): 레시피 매칭 단위. 같은 그룹의 재료는 레시피에서 서로 대체 가능 (예: 우유 그룹)
- **재고는 구매 건(lot) 단위로 저장**
  - 같은 재료라도 구매일이 다르면 소비기한이 다르므로 별도 행으로 저장하고, 화면에서만 재료별로 묶어서 표시
  - 한 건의 일부만 보관 위치를 바꾸면(소분) 두 건으로 나누고, 나뉜 건에 원래 건을 기록
- **레시피 분량은 텍스트로 보존하고, 차감량은 사용자가 선택**
  - 레시피 재료는 재료명·재료 그룹 매칭까지만 구조화하고 분량은 원문 텍스트로 저장
  - 완료 체크 시 재료별로 "다 씀 / 절반 / 조금 / 안 씀"을 선택하여 차감
- **인식 결과와 외부 데이터는 원본을 보존**
  - LLM 인식 원본과 사용자 수정 결과, 공공 레시피 API 원본 응답, RAG 추천의 LLM 응답 원본을 함께 저장
- **금액은 원(KRW) 단위 정수로 저장하고 스냅샷으로 기록**
  - 재고에는 품목별 실 결제 금액(purchase_price)을 저장
  - 소비·폐기·나눔 이벤트에는 발생 시점의 금액(구매 가격 × 변화 비율)을 저장하여, 이후 수량이 수정되어도 리포트 값이 바뀌지 않도록 함
  - 주문 단위 할인과 배송비는 품목에 배분하지 않고 캡처(주문) 단위로 별도 저장
- **이력은 삭제하지 않고 이벤트로 기록**
  - 재고 변경, 추천 노출, 점수 변화를 모두 이벤트로 남기고, 잘못된 처리는 반대 방향의 취소 이벤트로 바로잡음
  - 게시글·댓글은 소프트 삭제, 회원 탈퇴는 비활성화 방식
- **점수는 이벤트 합계로 계산하고 주간 점수에 캐시**
  - 점수 변화는 score_event에 사유와 함께 기록하고, 홈 화면용 현재 점수는 weekly_score에 함께 갱신
- **게시글은 공통 테이블 + 게시판별 상세 테이블**
  - 댓글·이미지·반응은 공통 게시글(post)에 연결하고, 피드와 나눔 전용 정보는 각 상세 테이블에 저장
- **날짜 기준은 한국 시간**
  - 시각은 TIMESTAMPTZ로 저장하고, 일·주 단위 집계와 주간 점수는 Asia/Seoul 기준으로 계산 (한 주 = 월요일 00:00 ~ 일요일 23:59)
- **리포트 계산은 View로 정의**
  - 식비·폐기 금액·활용률 계산식을 View로 고정하여 화면, API, 분석에서 같은 기준을 사용

---

## 1. 회원 데이터

```
회원 데이터는 로그인 정보와 프로필을 하나의 커스텀 User 테이블로 관리하고,
활동 지역은 시·군·구 기준 테이블을 참조합니다.

프로필 정보 중 가구 인원과 선호 요리 종류는 RAG 추천 프롬프트에,
활동 지역은 나눔 게시글의 기본 지역과 이후 동네 랭킹에 활용합니다.
```

### 회원 데이터 테이블 목록

| 테이블명 | 설명 |
| :--- | --- |
| user | 커스텀 User (로그인 정보 + 프로필) |
| region | 시·군·구 기준 목록 |

### 회원 데이터 테이블 명세

#### user

```
테이블명: user (Django 커스텀 User, AbstractUser 상속)

Primary Key: id

Foreign Key: region_code → region.region_code (NULL 허용)

Unique: email, nickname

설계 목적:
	- 로그인 정보와 프로필을 한 테이블에서 관리하여 조회를 단순화
	- 이메일 로그인(USERNAME_FIELD = email), 화면 표시는 닉네임

적재 규칙:
	- AbstractUser의 username 필드는 사용하지 않음
	- 비밀번호는 Django 해시로 저장 (확장 시 소셜 가입자는 사용할 수 없는 비밀번호로 설정)
	- 로그인 토큰은 DRF 기본 토큰 테이블(authtoken_token)에 저장 (MVP는 만료 없음)
	- 탈퇴 시 행을 삭제하지 않고 is_active = FALSE, withdrawn_at 기록,
	  닉네임은 "탈퇴한 사용자#{id}"로 변경, 이메일·프로필 이미지·소개는 비움
	- 비공개(is_public = FALSE)이면 피드 게시글과 점수는 팔로워에게만 노출 (나눔 게시글은 항상 공개)
	- preferred_cuisines 값은 공공 레시피의 요리 종류(recipe.dish_type)와 같은 값을 사용 (밥 / 국&찌개 / 반찬 / 일품 / 후식)
	- 점수·뱃지는 이 테이블에 저장하지 않고 weekly_score, user_badge에서 조회
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **id** | BIGSERIAL | N | PK | 사용자 식별자 | |
| **email** | VARCHAR(254) | Y | UQ | 로그인 이메일 | 탈퇴 시 NULL |
| **password** | VARCHAR(128) | N | | 비밀번호 해시 | Django 기본 |
| **nickname** | VARCHAR(20) | N | UQ | 닉네임 | |
| **profile_image_path** | VARCHAR(300) | Y | | 프로필 이미지 경로 | 외부 스토리지 |
| **bio** | VARCHAR(100) | Y | | 한 줄 소개 | |
| **household_size** | SMALLINT | Y | | 가구 인원 | 추천 인분 참고 |
| **preferred_cuisines** | JSONB | N | | 선호 요리 종류 | 예: ["국&찌개", "반찬"], 기본값 [] |
| **region_code** | VARCHAR(5) | Y | FK | 활동 지역 (시·군·구) | |
| **is_public** | BOOLEAN | N | | 프로필 공개 여부 | 기본값 TRUE |
| **is_active** | BOOLEAN | N | | 활성 여부 | 탈퇴 시 FALSE |
| **is_staff** | BOOLEAN | N | | 관리자 화면 접근 | Django 기본 |
| **is_superuser** | BOOLEAN | N | | 최고 관리자 | Django 기본 |
| **date_joined** | TIMESTAMPTZ | N | | 가입 시각 | |
| **last_login** | TIMESTAMPTZ | Y | | 마지막 로그인 | |
| **withdrawn_at** | TIMESTAMPTZ | Y | | 탈퇴 시각 | |

#### region

```
테이블명: region

Primary Key: region_code

설계 목적:
	- 활동 지역을 자유 텍스트가 아닌 코드로 관리하여 지역별 집계(동네 랭킹 등)가 가능하도록 함
	- 동 단위는 너무 세분화되어 사용자가 적을 때 의미가 없으므로 시·군·구 단위로 관리

적재 규칙:
	- 공공데이터포털의 행정구역(시·군·구) 코드 파일을 한 번 받아 시드 데이터로 적재 (실시간 API 호출 없음)
	- 행정구역 개편으로 사라진 지역은 삭제하지 않고 is_active = FALSE
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **region_code** | VARCHAR(5) | N | PK | 시·군·구 코드 | |
| **sido_name** | VARCHAR(20) | N | | 시·도명 | 예: 대전광역시 |
| **sigungu_name** | VARCHAR(20) | N | | 시·군·구명 | 예: 유성구 |
| **is_active** | BOOLEAN | N | | 사용 여부 | 기본값 TRUE |

---

## 2. 기준 데이터

```
기준 데이터는 서비스 전체에서 공통으로 참조하는 마스터 데이터입니다.
재료 정규화, 소비기한 산정, 레시피 매칭이 모두 이 테이블을 기준으로 동작합니다.

식약처 소비기한 참고값은 오픈 API로 제공되지 않고 가공식품 위주이므로,
자주 구매하는 재료 100~150개를 직접 구축합니다.
가공식품은 식약처 참고값 안내서를, 신선식품은 일반 보관 기준을 참고하며,
LLM으로 초안을 만든 뒤 사람이 검수하여 Django Admin으로 관리합니다.
```

### 기준 데이터 테이블 목록

| 테이블명 | 설명 |
| :--- | --- |
| ingredient_group | 레시피 매칭 단위의 재료 그룹 |
| ingredient | 소비기한 관리 단위의 표준 재료 |
| product_alias | 상품명 → 표준 재료 매핑 사전 |

### 기준 데이터 테이블 명세

#### ingredient_group

```
테이블명: ingredient_group

Primary Key: group_id

Unique: group_name

설계 목적:
	- 레시피 재료가 참조하는 매칭 단위
	- 같은 그룹에 속한 표준 재료는 레시피에서 서로 대체 가능한 것으로 간주
	- 레시피마다 대체 재료를 따로 정의하지 않아도 되도록 설계
	- 냉장고 그림의 재료 그림(icon)과 칸 배치(category)의 기준

적재 규칙:
	- 레시피에서 부르는 일반적인 이름을 그룹명으로 사용 (예: 우유, 계란, 양파)
	- 그룹 간 대체(버터 ↔ 마가린 등)는 MVP 범위에서 제외
	- icon은 프론트 재료 그림의 키 (예: tofu, milk), 없으면 NULL로 두고 분류 기본 그림 사용
	- 냉장 보관 재료의 칸 배치: category가 채소·과일이면 채소칸, 음료·소스·양념이면 도어, 나머지는 냉장 선반 (API에서 계산)
	- is_featured = TRUE인 그룹을 비회원 시작 화면의 기본 재료 칩(20개 안팎)으로 노출
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **group_id** | BIGSERIAL | N | PK | 재료 그룹 식별자 | |
| **group_name** | VARCHAR(50) | N | UQ | 그룹명 | 예: 우유 |
| **category** | VARCHAR(30) | N | | 상위 분류 | 채소·과일, 육류, 유제품·계란, 음료·소스·양념 등 |
| **icon** | VARCHAR(30) | Y | | 재료 그림 키 | 예: tofu, milk |
| **is_featured** | BOOLEAN | N | | 시작 화면 기본 칩 여부 | 기본값 FALSE |
| **created_at** | TIMESTAMPTZ | N | | 생성 시각 | |

#### ingredient

```
테이블명: ingredient

Primary Key: ingredient_id

Foreign Key: group_id → ingredient_group.group_id

Unique: ingredient_name

설계 목적:
	- 재고에 등록되는 실제 재료 단위이자 소비기한 기준값의 단위
	- 보관 위치별 소비기한 일수와 개봉 후 일수를 함께 관리하여 보관 상태 변경 시 재계산에 활용
	- 수량 관리 방식(count / amount / presence)을 재료별로 지정

적재 규칙:
	- 소비기한 기준값 또는 기본 보관 위치가 다르면 별도 재료로 분리
	- 기준값 출처를 expiry_basis로 구분 (mfds_ref: 식약처 참고값 / general: 일반 보관 기준 / adjusted: 사용 이력으로 보정)
	- 해당 보관 방식이 적합하지 않은 경우 일수를 NULL로 둠 (예: 계란 냉동) → 그 보관 위치로는 옮길 수 없음
	- presence 재료(양념류)는 default_unit을 NULL로 두고 완료 체크 차감 대상에서 제외
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **ingredient_id** | BIGSERIAL | N | PK | 표준 재료 식별자 | |
| **group_id** | BIGINT | N | FK | 재료 그룹 | 레시피 매칭에 사용 |
| **ingredient_name** | VARCHAR(50) | N | UQ | 표준 재료명 | 예: 저지방우유 |
| **default_storage** | VARCHAR(10) | N | | 기본 보관 위치 | fridge / freezer / room |
| **fridge_days** | SMALLINT | Y | | 냉장 보관 시 소비기한 일수 | |
| **freezer_days** | SMALLINT | Y | | 냉동 보관 시 소비기한 일수 | |
| **room_days** | SMALLINT | Y | | 실온 보관 시 소비기한 일수 | |
| **opened_days** | SMALLINT | Y | | 개봉 후 소비기한 일수 | 개봉 개념이 없으면 NULL |
| **expiry_basis** | VARCHAR(10) | N | | 기준값 출처 | mfds_ref / general / adjusted |
| **quantity_mode** | VARCHAR(10) | N | | 수량 관리 방식 | count / amount / presence |
| **default_unit** | VARCHAR(5) | Y | | 표준 단위 | 개 / g / ml, presence는 NULL |
| **created_at** | TIMESTAMPTZ | N | | 생성 시각 | |
| **updated_at** | TIMESTAMPTZ | N | | 수정 시각 | 기준값 보정 추적용 |

#### product_alias

```
테이블명: product_alias

Primary Key: alias_id

Foreign Key: ingredient_id → ingredient.ingredient_id

Unique: alias_text

설계 목적:
	- 캡처에서 인식된 상품명을 표준 재료로 매핑하는 사전
	- 사용자가 확인 화면에서 확정한 매핑을 누적하여 정규화 정확도를 점진적으로 개선
	- 이후 임베딩 유사도 기반 정규화의 학습·평가 데이터로 활용

적재 규칙:
	- alias_text는 공백 정리 및 소문자 처리 후 저장
	- source로 매핑 출처를 구분 (seed: 초기 구축 / llm: LLM 제안 / user: 사용자 확정)
	- 동일 상품명이 다시 확정되면 confirmed_count를 증가
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **alias_id** | BIGSERIAL | N | PK | 매핑 식별자 | |
| **alias_text** | VARCHAR(200) | N | UQ | 정제된 상품명 | 예: 곰곰 무항생제 대란 30구 |
| **ingredient_id** | BIGINT | N | FK | 매핑된 표준 재료 | |
| **source** | VARCHAR(10) | N | | 매핑 출처 | seed / llm / user |
| **confirmed_count** | INT | N | | 사용자 확정 횟수 | 기본값 0 |
| **created_at** | TIMESTAMPTZ | N | | 생성 시각 | |

---

## 3. 레시피 데이터

```
레시피 데이터는 식품안전나라 조리식품 레시피 DB(COOKRCP01, 약 1,150건)와
사용자가 피드에 공유한 레시피를 같은 구조로 저장하는 영역입니다.

공공 레시피의 재료 정보는 하나의 문자열로 제공되고 형식이 레시피마다 다르므로
(예: "●양념장 :", "[1인분]", 첫 줄의 메뉴명 반복),
적재 시 LLM으로 재료를 한 줄씩 분리하고 재료 그룹에 매칭한 뒤 Admin에서 검수합니다.
분량은 숫자로 변환하지 않고 원문 텍스트로 보존합니다.

RAG 검색을 위해 메뉴명과 재료 문자열을 임베딩하여 pgvector 컬럼에 저장합니다.
```

### 외부 데이터 수집 기준 (COOKRCP01)

| 항목 | 내용 |
| :--- | --- |
| 제공처 | 식품의약품안전처, 식품안전나라 오픈API |
| 호출 형식 | `/api/{인증키}/COOKRCP01/json/{시작}/{끝}` (요리 종류 필터: `/RCP_PAT2={값}`) |
| 인증 | 식품안전나라 인증키 발급 필요 (sample 키는 최대 5건) |
| 수집 범위 | 전체 약 1,156건, 1회 최대 1,000건이므로 2회 호출로 전체 수집 |
| 갱신 | 상시 갱신 데이터이므로 주기적 재수집 시 source_recipe_id 기준으로 변경분만 반영 |
| 주의 사항 | 이미지 URL은 http로 제공되므로 https로 변환하여 저장, 조리 순서 끝의 잔여 문자(a, b, c 등) 정제, 요리 종류 분류는 거칠어 강한 필터가 아닌 참고값으로 사용 |

| 원본 필드 | 저장 위치 | 비고 |
| :--- | --- | --- |
| RCP_SEQ | recipe.source_recipe_id | |
| RCP_NM | recipe.recipe_name | |
| RCP_WAY2 | recipe.cooking_method | 끓이기, 찌기, 굽기 등 |
| RCP_PAT2 | recipe.dish_type | 반찬, 국&찌개, 후식, 일품, 밥 등 (user.preferred_cuisines와 같은 값) |
| RCP_PARTS_DTLS | recipe_ingredient.raw_text (LLM 분리) | 원문 전체는 raw_payload에 보존 |
| MANUAL01~20, MANUAL_IMG01~20 | recipe.steps | 빈 단계 제외, 순서대로 배열 |
| ATT_FILE_NO_MAIN | recipe.image_url | https 변환 |
| RCP_NA_TIP | recipe.tip | 저감 조리법 팁 |
| INFO_ENG 등 영양 정보 | recipe.raw_payload | MVP에서는 사용하지 않음 |

### 레시피 데이터 테이블 목록

| 테이블명 | 설명 |
| :--- | --- |
| recipe | 레시피 기본 정보 및 임베딩 (공공 / 사용자) |
| recipe_ingredient | 레시피별 재료 (재료명, 재료 그룹, 분량 텍스트) |

### 레시피 데이터 테이블 명세

#### recipe

```
테이블명: recipe

Primary Key: recipe_id

Foreign Key: author_id → user.id (NULL 허용)

Unique: (source, source_recipe_id) — source = public인 행에만 적용 (부분 유니크 인덱스)

Indexes:
	- idx_recipe_embedding (embedding): pgvector 유사도 검색용 (HNSW 등)

설계 목적:
	- 추천 후보와 사용자 공유 레시피를 같은 구조로 저장하여 상세 화면, 완료 체크, 피드 연결을 공통으로 처리
	- 원본 API 응답을 JSONB로 보존하여 재파싱 및 컬럼 추가에 대응
	- 임베딩 원문 해시를 저장하여 레시피 수정·모델 변경 시 필요한 행만 재임베딩

적재 규칙:
	- source로 출처를 구분 (public: COOKRCP01 / user: 사용자 공유)
	- 공공 레시피는 author_id를 NULL, 사용자 레시피는 source_recipe_id와 raw_payload를 NULL로 둠
	- 조리 순서는 단계별 배열(JSONB)로 저장: [{order, text, image_url}]
	- is_recommendable: RAG 추천 후보 포함 여부 (공공 레시피 기본 TRUE, 사용자 레시피는 MVP에서 FALSE)
	- is_active: 사용 여부 (재료 매칭이 부실한 공공 레시피, 삭제된 게시글의 사용자 레시피는 FALSE)
	- 레시피가 비활성화되어도 이미 완료한 기록(recipe_completion)은 그대로 유지
	- embedding_text = 메뉴명 + 요리 종류 + 재료명 목록, 이 텍스트의 SHA-256 해시를 embedding_text_hash에 저장
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **recipe_id** | BIGSERIAL | N | PK | 레시피 식별자 | |
| **source** | VARCHAR(10) | N | UQ | 출처 | public / user |
| **source_recipe_id** | VARCHAR(20) | Y | UQ | 원본 레시피 일련번호 | RCP_SEQ, 사용자 레시피는 NULL |
| **author_id** | BIGINT | Y | FK | 작성자 | 공공 레시피는 NULL |
| **recipe_name** | VARCHAR(100) | N | | 메뉴명 | |
| **cooking_method** | VARCHAR(20) | Y | | 조리 방법 | 끓이기, 볶기 등 |
| **dish_type** | VARCHAR(20) | Y | | 요리 종류 | 반찬, 국&찌개, 후식, 일품, 밥 등 |
| **steps** | JSONB | N | | 조리 순서 | [{order, text, image_url}] |
| **image_url** | VARCHAR(300) | Y | | 대표 이미지 | https로 저장 |
| **servings** | SMALLINT | N | | 기준 인분 | 기본값 1 |
| **tip** | TEXT | Y | | 조리 팁 | |
| **raw_payload** | JSONB | Y | | 원본 API 응답 | 공공 레시피만 |
| **is_recommendable** | BOOLEAN | N | | RAG 추천 후보 여부 | |
| **is_active** | BOOLEAN | N | | 사용 여부 | 기본값 TRUE |
| **embedding** | VECTOR | Y | | 레시피 임베딩 | 차원은 임베딩 모델 선정 후 확정 |
| **embedding_model** | VARCHAR(50) | Y | | 임베딩 모델명 | |
| **embedding_text_hash** | CHAR(64) | Y | | 임베딩 원문 해시 | 재임베딩 판단용 |
| **created_at** | TIMESTAMPTZ | N | | 생성 시각 | |
| **updated_at** | TIMESTAMPTZ | N | | 수정 시각 | |

#### recipe_ingredient

```
테이블명: recipe_ingredient

Primary Key: recipe_ingredient_id

Foreign Key:
	- recipe_id → recipe.recipe_id
	- group_id → ingredient_group.group_id (NULL 허용)

그레인(1행 정의): 1 row = 1 레시피의 재료 1개

설계 목적:
	- 레시피 재료를 재료 그룹과 연결하여 보유 재료 표시("5개 중 4개 보유"), RAG 검색 키워드, 완료 체크 대상 재료 판별, 비회원 레시피 매칭에 사용
	- 분량은 화면 표시용 원문 텍스트로만 보존 (차감량은 완료 체크 시 사용자가 선택)

적재 규칙:
	- 공공 레시피: LLM이 원문 재료 문자열을 재료 단위로 분리하고 재료명·분량 텍스트·구분(주재료/양념 등)·재료 그룹을 제안, Admin에서 검수
	- 사용자 레시피: 작성 화면에서 "재료명 + 분량 텍스트"를 한 줄씩 입력, 재료명은 자동완성으로 재료 그룹에 연결 (목록에 없는 재료는 그룹 NULL)
	- 그룹 매칭에 실패한 재료는 group_id를 NULL로 두고 보유 재료 계산에서 제외
	- 양념류 등 보유 여부 계산에서 비중을 낮출 재료는 is_seasoning으로 구분
	- match_source로 매칭 출처를 구분 (llm / manual / user)
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **recipe_ingredient_id** | BIGSERIAL | N | PK | 레시피 재료 식별자 | |
| **recipe_id** | BIGINT | N | FK | 레시피 | |
| **group_id** | BIGINT | Y | FK | 매칭된 재료 그룹 | 매칭 실패 시 NULL |
| **section** | VARCHAR(20) | Y | | 재료 구분 | 주재료, 양념장, 고명 등 |
| **raw_text** | VARCHAR(100) | N | | 원본 재료 문자열 | 예: 양파 10g(3×1cm) |
| **ingredient_name** | VARCHAR(50) | N | | 재료명 | 예: 양파 |
| **amount_text** | VARCHAR(50) | Y | | 분량 텍스트 | 예: 10g(3×1cm), 약간 |
| **is_seasoning** | BOOLEAN | N | | 양념 여부 | 기본값 FALSE |
| **is_optional** | BOOLEAN | N | | 선택 재료 여부 | 기본값 FALSE |
| **match_source** | VARCHAR(10) | N | | 매칭 출처 | llm / manual / user |
| **sort_order** | SMALLINT | N | | 표시 순서 | |

---

## 4. 입력 데이터

```
입력 데이터는 사용자가 업로드한 캡처 이미지와 인식 결과를 저장하는 영역입니다.

인식 결과는 LLM이 추출한 원본 값과, 사용자가 확인 화면에서 수정한 확정 값을
같은 행에 함께 저장합니다.
두 값의 차이를 비교하여 인식 정확도와 정규화 정확도를 측정합니다.
```

### 입력 데이터 테이블 목록

| 테이블명 | 설명 |
| :--- | --- |
| capture | 캡처 이미지 및 인식 처리 상태 |
| capture_item | 캡처에서 인식된 품목 (원본 / 확정본) |

### 입력 데이터 테이블 명세

#### capture

```
테이블명: capture

Primary Key: capture_id

Foreign Key: user_id → user.id

설계 목적:
	- 캡처 이미지 원본 경로와 인식 처리 상태를 관리
	- LLM 응답 원본과 모델 정보를 보존하여 프롬프트·모델 변경 시 비교에 활용

적재 규칙:
	- 이미지 파일은 외부 스토리지에 저장하고 경로만 저장
	- 인식은 업로드 요청 안에서 동기로 처리 (서버 시간 제한 20초)
	- status 흐름: uploaded → recognized → confirmed (실패 시 failed)
	- 인식 실패 시 error_message를 저장하고 재처리 가능하도록 이미지는 보존
	- 확인 화면의 수정 내용은 저장 시 한 번에 반영 (확정 전 중간 저장 없음)
	- 주문 단위 금액(총 결제 금액, 할인, 배송비)은 품목에 배분하지 않고 이 테이블에만 저장
	- 총 결제 금액은 품목 금액 합계와 비교하여 인식 누락 검증에 활용
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **capture_id** | BIGSERIAL | N | PK | 캡처 식별자 | |
| **user_id** | BIGINT | N | FK | 사용자 | |
| **image_path** | VARCHAR(300) | N | | 이미지 저장 경로 | |
| **platform** | VARCHAR(20) | Y | | 인식된 구매처 | coupang, kurly 등 |
| **purchase_date** | DATE | Y | | 인식된 구매일 | 인식 실패 시 업로드일로 대체 가능 |
| **order_total_amount** | INT | Y | | 총 결제 금액 (원) | 품목 합계 검증용 |
| **order_discount_amount** | INT | Y | | 주문 단위 할인 금액 (원) | 쿠폰, 즉시할인 등 |
| **delivery_fee** | INT | Y | | 배송비 (원) | 식비 집계 별도 항목 |
| **status** | VARCHAR(10) | N | | 처리 상태 | uploaded / recognized / confirmed / failed |
| **llm_model** | VARCHAR(50) | Y | | 사용한 모델명 | |
| **prompt_version** | VARCHAR(20) | Y | | 프롬프트 버전 | |
| **llm_response** | JSONB | Y | | LLM 응답 원본 | |
| **error_message** | TEXT | Y | | 실패 사유 | |
| **created_at** | TIMESTAMPTZ | N | | 업로드 시각 | |
| **confirmed_at** | TIMESTAMPTZ | Y | | 사용자 확정 시각 | |

#### capture_item

```
테이블명: capture_item

Primary Key: capture_item_id

Foreign Key:
	- capture_id → capture.capture_id
	- predicted_ingredient_id → ingredient.ingredient_id
	- confirmed_ingredient_id → ingredient.ingredient_id

그레인(1행 정의): 1 row = 캡처 1장에서 인식된 상품 1개

설계 목적:
	- 인식 원본(predicted_*)과 사용자 확정값(confirmed_*)을 함께 저장
	- 상품명 인식 정확도, 재료 정규화 정확도, 수량·가격 인식 정확도를 행 단위로 측정

적재 규칙:
	- predicted_* 컬럼은 인식 직후 저장하고 이후 수정하지 않음
	- confirmed_* 컬럼은 사용자가 확인 화면에서 저장할 때 채움
	- 사용자가 식재료가 아니라고 제외한 상품은 is_excluded = TRUE로 남김 (삭제하지 않음)
	- 확정된 품목은 inventory_item으로 생성되며, 확정 상품명은 product_alias에 누적
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **capture_item_id** | BIGSERIAL | N | PK | 인식 품목 식별자 | |
| **capture_id** | BIGINT | N | FK | 캡처 | |
| **raw_product_name** | VARCHAR(200) | N | | 인식된 상품명 원문 | |
| **raw_quantity_text** | VARCHAR(50) | Y | | 인식된 수량 원문 | 예: 2L x 6, 30구 |
| **predicted_ingredient_id** | BIGINT | Y | FK | 예측 표준 재료 | 정규화 실패 시 NULL |
| **predicted_quantity** | NUMERIC(10,2) | Y | | 예측 수량 | 표준 단위 기준 |
| **predicted_unit** | VARCHAR(5) | Y | | 예측 단위 | |
| **predicted_price** | INT | Y | | 예측 품목 결제 금액 (원) | 품목 행 금액 |
| **confirmed_ingredient_id** | BIGINT | Y | FK | 확정 표준 재료 | |
| **confirmed_quantity** | NUMERIC(10,2) | Y | | 확정 수량 | |
| **confirmed_unit** | VARCHAR(5) | Y | | 확정 단위 | |
| **confirmed_price** | INT | Y | | 확정 품목 결제 금액 (원) | |
| **confirmed_storage** | VARCHAR(10) | Y | | 확정 보관 위치 | fridge / freezer / room |
| **is_excluded** | BOOLEAN | N | | 식재료 아님으로 제외 | 기본값 FALSE |

- **파생 지표 (평가용, 쿼리로 계산)**

| 지표명 | 설명 | 계산 기준 |
| :--- | --- | --- |
| **normalization_accuracy** | 재료 정규화 정확도 | predicted_ingredient_id = confirmed_ingredient_id 비율 (제외 품목 제외) |
| **quantity_accuracy** | 수량 인식 정확도 | predicted_quantity = confirmed_quantity AND 단위 일치 비율 |
| **price_accuracy** | 가격 인식 정확도 | predicted_price = confirmed_price 비율 |
| **exclusion_rate** | 비식재료 오인식 비율 | is_excluded = TRUE 비율 |

---

## 5. 재고 데이터

```
재고 데이터는 서비스의 핵심 계층으로, 추천·알림·리포트·점수·나눔의 단일 데이터 소스입니다.

재고는 구매 건(lot) 단위로 저장하며, 현재 상태는 inventory_item에,
모든 변경 내역은 inventory_event에 기록합니다.
현재 상태 테이블과 이벤트 테이블을 분리함으로써,
재고 조회는 빠르게 유지하면서 소비·폐기 패턴 분석, 점수 산정, 소비기한 기준값 보정에 필요한 이력을 보존합니다.
```

### 재고 데이터 테이블 목록

| 테이블명 | 설명 |
| :--- | --- |
| inventory_item | 사용자별 재고 현재 상태 (구매 건 단위) |
| inventory_event | 재고 변경 이력 (등록, 차감, 보관 변경, 소분, 소진, 폐기, 나눔, 확인 응답, 취소) |

### 재고 데이터 테이블 명세

#### inventory_item

```
테이블명: inventory_item

Primary Key: item_id

Foreign Key:
	- user_id → user.id
	- ingredient_id → ingredient.ingredient_id
	- capture_item_id → capture_item.capture_item_id (NULL 허용)
	- parent_item_id → inventory_item.item_id (NULL 허용)

그레인(1행 정의): 1 row = 사용자 1명의 재료 구매 1건 (소분하면 나뉜 1건)

Indexes:
	- idx_inventory_user_status_expiry (user_id, status, expected_expiry_date): 임박 재료 조회용

설계 목적:
	- 재료별 남은 양, 보관 상태, 예상 소비기한을 관리
	- 남은 비율(remaining / initial)로 화면의 단계(많음/반쯤/조금)를 계산

적재 규칙:
	- 캡처 확정 시 생성 (직접 추가한 재료는 capture_item_id가 NULL)
	- quantity_mode가 presence인 재료는 수량 컬럼을 NULL로 둠
	- 상태(status)는 active / used_up / discarded / shared 중 하나이며, 행은 삭제하지 않음
	- remaining_quantity가 0 이하가 되면 status를 used_up으로 변경
	- 나눔 게시글의 거래 상태가 완료되면 status를 shared로 변경
	- purchase_price는 capture_item.confirmed_price를 그대로 반영 (직접 추가 시 사용자 입력, 미입력 시 NULL)
	- 남은 가치(remaining_value) = purchase_price × remaining_quantity / initial_quantity (쿼리로 계산)

소분 규칙 (한 건의 일부만 보관 위치 변경):
	- 원래 건: initial_quantity·remaining_quantity를 옮긴 수량만큼 줄이고, purchase_price를 새 건 가격만큼 줄임
	- 새 건: 옮긴 수량으로 생성, purchase_price = 원래 가격 × (옮긴 수량 / 원래 initial_quantity)
	  (두 건의 가격 합은 원래 가격과 같아서 식비 집계가 바뀌지 않음)
	- 새 건의 purchase_date·capture_item_id는 원래 건과 같고, parent_item_id에 원래 건을 기록
	- 두 건 모두에 split 이벤트를 남기며, 다시 같은 보관 위치로 옮겨도 합치지 않음
	- presence 재료는 소분하지 않음

소비기한 산정 규칙:
	- 등록 시: purchase_date + 보관 위치별 일수 (ingredient.fridge_days 등)
	- 보관 위치 변경 시 (소분한 새 건도 같은 규칙):
		· 냉동으로 옮기면 변경일 + freezer_days
		· 그 외에는 MIN(현재 예상 소비기한, 변경일 + 새 보관 위치 일수) (보관 위치를 바꿔서 기한이 늘어나지 않도록)
		· 예상 소비기한이 지난 재고는 냉동으로 옮길 수 없음
	- 개봉 시: MIN(현재 예상 소비기한, 개봉일 + opened_days)
	- 사용자가 직접 날짜를 수정하면 expiry_source = manual로 표시하고 자동 재계산 대상에서 제외
	- 임박 기준: 예상 소비기한까지 남은 일수가 3일 이하 (점수 규칙의 조건 값과 동일하게 관리)
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **item_id** | BIGSERIAL | N | PK | 재고 식별자 | |
| **user_id** | BIGINT | N | FK | 사용자 | |
| **ingredient_id** | BIGINT | N | FK | 표준 재료 | |
| **capture_item_id** | BIGINT | Y | FK | 원본 인식 품목 | 직접 추가 시 NULL |
| **parent_item_id** | BIGINT | Y | FK | 소분 전 원래 재고 | 소분한 새 건만 |
| **purchase_date** | DATE | N | | 구매일 | |
| **initial_quantity** | NUMERIC(10,2) | Y | | 최초 수량 | presence 재료는 NULL |
| **remaining_quantity** | NUMERIC(10,2) | Y | | 남은 수량 | presence 재료는 NULL |
| **unit** | VARCHAR(5) | Y | | 표준 단위 | 개 / g / ml |
| **purchase_price** | INT | Y | | 구매 가격 (원) | 품목 실 결제 금액 |
| **storage** | VARCHAR(10) | N | | 현재 보관 위치 | fridge / freezer / room |
| **is_opened** | BOOLEAN | N | | 개봉 여부 | 기본값 FALSE |
| **opened_at** | DATE | Y | | 개봉일 | |
| **expected_expiry_date** | DATE | N | | 예상 소비기한 | |
| **expiry_source** | VARCHAR(10) | N | | 소비기한 산정 출처 | auto / manual |
| **status** | VARCHAR(10) | N | | 재고 상태 | active / used_up / discarded / shared |
| **last_checked_at** | TIMESTAMPTZ | Y | | 마지막 "아직 있나요?" 응답 시각 | 방치 감점 중단 판단 |
| **created_at** | TIMESTAMPTZ | N | | 등록 시각 | |
| **updated_at** | TIMESTAMPTZ | N | | 수정 시각 | |

- **화면 표시 단계 (API에서 계산)**

| 단계 | 기준 | 적용 대상 |
| :--- | --- | --- |
| 개수 표시 | remaining_quantity 그대로 표시 | quantity_mode = count |
| 많음 / 반쯤 / 조금 | remaining / initial 비율 (0.6 이상 / 0.3 이상 / 0.3 미만) | quantity_mode = amount |
| 있음 | status = active | quantity_mode = presence |

- 사용자가 단계 버튼으로 남은 양을 고치면 처음 양의 80% / 50% / 20%로 저장합니다. (이미 그 단계 안이면 바꾸지 않음)
- 냉장고 그림의 칸(zone)은 storage와 ingredient_group.category로 API에서 계산하며 저장하지 않습니다. (냉장고 안 칸끼리 끌어서 옮긴 위치도 저장하지 않음)

#### inventory_event

```
테이블명: inventory_event

Primary Key: event_id

Foreign Key:
	- item_id → inventory_item.item_id
	- completion_id → recipe_completion.completion_id (NULL 허용)
	- post_id → post.post_id (NULL 허용)
	- reverted_event_id → inventory_event.event_id (NULL 허용)
	- related_item_id → inventory_item.item_id (NULL 허용)

그레인(1행 정의): 1 row = 재고 1건에 발생한 변경 1회

Indexes:
	- idx_inventory_event_item (item_id, created_at): 재고별 이력 조회용
	- idx_inventory_event_type_time (event_type, created_at): 일·주 단위 리포트 집계용

설계 목적:
	- 재고의 모든 변경을 이벤트로 기록하여 재고 정합성 추적
	- 소비·폐기·나눔 금액을 발생 시점에 기록하여 리포트와 점수의 원천 데이터로 사용
	- "아직 있나요?" 응답과 소진·폐기 시점을 분석하여 재료별 소비기한 기준값 보정에 활용

적재 규칙:
	- event_type별 기록 내용
		· created: 재고 등록
		· consumed: 레시피 완료에 따른 차감 (completion_id, usage_level 기록)
		· adjusted: 사용자의 남은 양 수정 (줄이기·늘리기)
		· storage_changed: 보관 위치 변경 (구매 건 통째로)
		· split: 소분 (원래 건과 새 건 모두에 기록, related_item_id로 상대 건 연결)
		· opened: 개봉 처리
		· used_up: 직접 다 씀 처리
		· discarded: 버림 처리
		· shared: 나눔 완료 처리 (post_id 연결)
		· check_response: 기한 경과 확인 응답
		· reverted: 잘못된 처리의 취소 (reverted_event_id로 원래 이벤트 연결)
	- consumed의 usage_level과 차감량
		· amount 재료: all / half / little = 현재 남은 양의 100% / 50% / 25% 차감 (none은 이벤트를 만들지 않음)
		· count 재료: 사용자가 입력한 개수만큼 차감 (usage_level = count)
		· presence 재료: 차감하지 않음
	- quantity_delta는 수량 변화량(차감은 음수)을 기록
	- value_delta는 수량이 줄어드는 이벤트(consumed, adjusted, used_up, discarded, shared)에서
	  purchase_price × (줄어든 수량 / initial_quantity)로 계산하여 발생 시점에 저장
	- adjusted로 남은 양을 늘리면(처음 양까지만) 늘어난 만큼을 같은 식으로 계산해 value_delta를 음수로 기록
	  (앞선 소진 기록을 바로잡는 것으로 보며, 리포트 합계에 그대로 포함, 점수에는 영향 없음)
	- split은 소비가 아니므로 value_delta를 NULL로 두고, quantity_delta에 옮긴 수량(원래 건은 음수, 새 건은 양수)을 기록
	- presence 재료는 수량 비율을 알 수 없으므로 used_up·discarded·shared 시 purchase_price 전액을 기록
	- check_response로 used_up·discarded 응답을 받으면 해당 event_type의 이벤트를 함께 생성하여 금액 집계 기준을 하나로 유지
	- check_response는 response 컬럼에 still_have / used_up / discarded 중 하나를 기록
	- reverted는 원래 이벤트의 quantity_delta·value_delta를 반대 부호로 기록하고, 재고 상태를 원래대로 되돌림
	  (취소 대상: consumed, adjusted, used_up, discarded / storage_changed·split·opened는 취소하지 않음)
	- 이벤트는 수정·삭제하지 않음
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **event_id** | BIGSERIAL | N | PK | 이벤트 식별자 | |
| **item_id** | BIGINT | N | FK | 재고 | |
| **event_type** | VARCHAR(20) | N | | 이벤트 유형 | 적재 규칙 참고 |
| **usage_level** | VARCHAR(10) | Y | | 사용량 선택 | all / half / little / count (consumed 시) |
| **quantity_delta** | NUMERIC(10,2) | Y | | 수량 변화량 | |
| **value_delta** | INT | Y | | 금액 변화량 (원) | 소비·폐기·나눔 금액 스냅샷, 양을 늘리면 음수 |
| **storage_before** | VARCHAR(10) | Y | | 변경 전 보관 위치 | storage_changed·split 시 |
| **storage_after** | VARCHAR(10) | Y | | 변경 후 보관 위치 | storage_changed·split 시 |
| **expiry_before** | DATE | Y | | 변경 전 예상 소비기한 | |
| **expiry_after** | DATE | Y | | 변경 후 예상 소비기한 | |
| **days_left** | SMALLINT | Y | | 이벤트 시점의 남은 일수 | 임박 소진 판단·분석용 |
| **response** | VARCHAR(15) | Y | | 확인 응답 | still_have / used_up / discarded |
| **completion_id** | BIGINT | Y | FK | 연결된 레시피 완료 | consumed 시 |
| **post_id** | BIGINT | Y | FK | 연결된 나눔 게시글 | shared 시 |
| **reverted_event_id** | BIGINT | Y | FK | 취소 대상 이벤트 | reverted 시 |
| **related_item_id** | BIGINT | Y | FK | 소분 상대 재고 | split 시 |
| **created_at** | TIMESTAMPTZ | N | | 발생 시각 | |

---

## 6. 추천 데이터

```
추천 데이터는 RAG 레시피 추천의 요청·검색·생성 과정과
추천 결과의 노출·클릭·완료를 기록하는 영역입니다.

추천 요청 1회마다 입력 스냅샷, 검색 후보, LLM 응답 원본, 성능 지표를 저장하여
검색 품질, 추천 성과, LLM 신뢰성, 비용·속도를 측정합니다.
노출 시점의 정보는 이후 재현할 수 없으므로 MVP 단계부터 저장하며,
이후 개인화 랭킹 모델(CatBoost)의 학습 데이터로도 사용합니다.

접속 시 띄우는 "오늘의 냉장고" 카드의 추천도 같은 테이블에 기록합니다.
비회원 레시피 보기(시작 화면)는 키워드 매칭만 사용하며 기록을 남기지 않습니다.
```

### 추천 데이터 테이블 목록

| 테이블명 | 설명 |
| :--- | --- |
| recommendation_request | RAG 추천 요청 1회의 입력·검색·생성 기록 |
| recommendation_impression | 추천 노출 로그 (노출 1회 = 레시피 1개) |
| recipe_completion | 레시피 완료 체크 로그 |

### 추천 데이터 테이블 명세

#### recommendation_request

```
테이블명: recommendation_request

Primary Key: request_id

Foreign Key:
	- user_id → user.id
	- cached_from → recommendation_request.request_id (NULL 허용)

Indexes:
	- idx_request_user_time (user_id, created_at): 사용자별 요청 조회용
	- idx_request_welcome (user_id, trigger, meal_slot, created_at): 오늘 시간대별 환영 카드 노출 여부 확인용
	- idx_request_cache (user_id, inventory_hash, created_at): 캐시 조회용

설계 목적:
	- RAG 추천 1회의 입력(재고 스냅샷), 검색 결과(후보), 생성 결과(LLM 응답)를 함께 보존
	- 검색 품질, LLM 검증 오류, 대체 추천 비율, 응답 시간, 토큰 사용량을 측정

적재 규칙:
	- trigger로 요청 경로를 구분 (welcome: 오늘의 냉장고 카드 / home: 홈 추천 / refresh: 새로고침 / ingredient: 특정 재료로 추천)
	- meal_slot은 한국 시간 기준 시간대 (breakfast 05~10시 / lunch 10~14시 / snack 14~17시, 22~05시 / dinner 17~22시)
	- input_snapshot: 임박 재료 [{item_id, ingredient_id, days_left, remaining_value}], 보유 재료 그룹 목록
	- inventory_hash: 임박 재료와 보유 재료 그룹 조합의 해시, 같은 날 같은 해시의 성공 요청이 있으면 결과를 재사용 (cache_hit = TRUE, cached_from 연결)
	- candidates: 검색 후보 [{recipe_id, similarity, keyword_hit, rank}]
	- LLM 응답에 후보 밖 recipe_id가 있으면 validation_errors에 기록하고 해당 항목은 제외
	- LLM 호출 실패 또는 유효 항목이 없으면 검색 상위 후보로 대체 추천하고 status = fallback
	- 환영 카드에서 "오늘은 그만 보기"를 누르면 dismissed = TRUE, 같은 날에는 환영 카드를 다시 띄우지 않음
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **request_id** | UUID | N | PK | 추천 요청 식별자 | |
| **user_id** | BIGINT | N | FK | 사용자 | |
| **trigger** | VARCHAR(15) | N | | 요청 경로 | welcome / home / refresh / ingredient |
| **meal_slot** | VARCHAR(10) | Y | | 시간대 | breakfast / lunch / snack / dinner |
| **input_snapshot** | JSONB | N | | 입력 재고 스냅샷 | |
| **inventory_hash** | CHAR(64) | N | | 재고 조합 해시 | 캐시 키 |
| **retrieval_version** | VARCHAR(20) | N | | 검색 방식 버전 | 예: hybrid_v1 |
| **candidates** | JSONB | Y | | 검색 후보 목록 | |
| **llm_model** | VARCHAR(50) | Y | | LLM 모델명 | |
| **prompt_version** | VARCHAR(20) | Y | | 프롬프트 버전 | |
| **llm_response** | JSONB | Y | | LLM 응답 원본 | |
| **validation_errors** | JSONB | Y | | 검증 오류 | 후보 밖 ID 등 |
| **status** | VARCHAR(10) | N | | 처리 상태 | success / fallback / failed |
| **cache_hit** | BOOLEAN | N | | 캐시 사용 여부 | 기본값 FALSE |
| **cached_from** | UUID | Y | FK | 재사용한 원래 요청 | |
| **retrieval_ms** | INT | Y | | 검색 소요 시간 (ms) | |
| **llm_ms** | INT | Y | | LLM 응답 시간 (ms) | |
| **input_tokens** | INT | Y | | 입력 토큰 수 | |
| **output_tokens** | INT | Y | | 출력 토큰 수 | |
| **dismissed** | BOOLEAN | N | | 오늘은 그만 보기 | welcome만 사용, 기본값 FALSE |
| **created_at** | TIMESTAMPTZ | N | | 요청 시각 | |

#### recommendation_impression

```
테이블명: recommendation_impression

Primary Key: impression_id

Foreign Key:
	- request_id → recommendation_request.request_id
	- user_id → user.id
	- recipe_id → recipe.recipe_id

그레인(1행 정의): 1 row = 1회 추천 요청에서 노출된 레시피 1개

Indexes:
	- idx_impression_request (request_id): 요청 단위 조회용

설계 목적:
	- 최종 노출 순위, 추천 이유, 사용될 임박 재료를 저장하여 추천 화면 표시와 성과 측정에 사용
	- 클릭·완료 여부를 라벨로 사용 (선택되지 않은 노출 = 부정 샘플)

적재 규칙:
	- rank는 LLM이 정한 최종 순서 (fallback이면 검색 순서)
	- 오늘의 냉장고 카드는 실제로 보여준 레시피만 노출로 기록 (처음 1개, "다른 추천 보기"를 누를 때마다 다음 순위 1개)
	- features에는 노출 시점의 매칭 재료 수, 임박 재료 수, 최소 남은 일수, 검색 유사도 등을 저장
	- 사용자가 추천 카드에서 레시피 상세로 이동하면 is_clicked = TRUE (클릭 기록 API)
	- 완료 여부는 recipe_completion과 조인하여 판단
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **impression_id** | BIGSERIAL | N | PK | 노출 식별자 | |
| **request_id** | UUID | N | FK | 추천 요청 | |
| **user_id** | BIGINT | N | FK | 사용자 | |
| **recipe_id** | BIGINT | N | FK | 노출된 레시피 | |
| **rank** | SMALLINT | N | | 노출 순위 | 1부터 시작 |
| **reason** | TEXT | Y | | 추천 이유 | LLM 생성 문구 |
| **used_items** | JSONB | Y | | 사용될 임박 재료 | [item_id] |
| **features** | JSONB | N | | 노출 시점 피처 | |
| **is_clicked** | BOOLEAN | N | | 상세 조회 여부 | 기본값 FALSE |
| **created_at** | TIMESTAMPTZ | N | | 노출 시각 | |

#### recipe_completion

```
테이블명: recipe_completion

Primary Key: completion_id

Foreign Key:
	- user_id → user.id
	- recipe_id → recipe.recipe_id
	- impression_id → recommendation_impression.impression_id (NULL 허용)

설계 목적:
	- 레시피 완료 체크를 기록하고 재고 차감·점수 산정의 기준으로 사용
	- 추천 노출과 연결하여 추천 성과(노출 대비 완료율)를 측정
	- 피드 자랑 글과 연결하여 "이 요리로 아낀 재료·금액"을 표시

적재 규칙:
	- 완료 확인 화면에서 레시피 재료 중 보유 재고만 표시하고, 같은 재료 그룹의 재고가 여러 건이면 예상 소비기한이 빠른 것을 기본 선택
	- 재료별 사용량 선택에 따라 inventory_event(consumed)를 생성하고 completion_id로 연결
	- 차감된 이벤트의 value_delta 합계와 임박 재료 수를 요약 컬럼에 저장 (피드 배지·점수 사유 표시용)
	- 추천을 거치지 않고 검색·피드에서 완료한 경우 impression_id는 NULL
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **completion_id** | BIGSERIAL | N | PK | 완료 식별자 | |
| **user_id** | BIGINT | N | FK | 사용자 | |
| **recipe_id** | BIGINT | N | FK | 완료한 레시피 | |
| **impression_id** | BIGINT | Y | FK | 연결된 추천 노출 | |
| **servings** | NUMERIC(4,1) | N | | 만든 인분 | 기본값 1 |
| **used_value** | INT | N | | 소진한 재고 금액 합계 (원) | 기본값 0 |
| **expiring_used_cnt** | SMALLINT | N | | 소진한 임박 재료 수 | 기본값 0 |
| **created_at** | TIMESTAMPTZ | N | | 완료 시각 | |

---

## 7. 커뮤니티 데이터

```
커뮤니티 데이터는 피드(인스타그램형)와 나눔 게시판(당근마켓형)을 하나의 공통 게시글 구조로 관리합니다.

화면은 게시판별로 완전히 분리하되, 댓글·이미지·반응·삭제·알림 같은 공통 기능은
공통 게시글(post)에 한 번만 구현하고,
게시판 전용 정보는 feed_detail, share_detail에 1:1로 저장합니다.
이후 Q&A 등 게시판을 추가할 때도 상세 테이블만 추가합니다.
```

### 커뮤니티 데이터 테이블 목록

| 테이블명 | 설명 |
| :--- | --- |
| post | 공통 게시글 |
| feed_detail | 피드 전용 정보 (자랑 / 레시피 공유) |
| share_detail | 나눔·교환 전용 정보 |
| post_image | 게시글 이미지 (최대 5장) |
| comment | 댓글 및 1단계 대댓글 |
| post_reaction | 반응 (피드: 좋아요 / 나눔: 관심) |
| follow | 팔로우 관계 |

### 커뮤니티 데이터 테이블 명세

#### post

```
테이블명: post

Primary Key: post_id

Foreign Key: author_id → user.id

Indexes:
	- idx_post_board_time (board, is_deleted, created_at): 게시판별 최신순 목록 조회용
	- idx_post_author_time (author_id, created_at): 팔로우 피드·프로필 조회용

설계 목적:
	- 게시판 공통 정보와 공통 기능(댓글, 이미지, 반응, 알림)의 기준 테이블

적재 규칙:
	- board로 게시판을 구분 (feed / share)
	- 게시글 1건마다 board에 맞는 상세 테이블 1행을 함께 생성
	- 삭제 시 행을 지우지 않고 is_deleted = TRUE, deleted_at 기록 (목록·상세에서 제외, 댓글은 보존)
	- 피드 게시글의 공개 범위는 작성자의 user.is_public을 따름 (나눔 게시글은 항상 공개)
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **post_id** | BIGSERIAL | N | PK | 게시글 식별자 | |
| **author_id** | BIGINT | N | FK | 작성자 | |
| **board** | VARCHAR(10) | N | | 게시판 | feed / share |
| **content** | TEXT | N | | 본문 | |
| **is_deleted** | BOOLEAN | N | | 삭제 여부 | 기본값 FALSE |
| **deleted_at** | TIMESTAMPTZ | Y | | 삭제 시각 | |
| **created_at** | TIMESTAMPTZ | N | | 작성 시각 | |
| **updated_at** | TIMESTAMPTZ | N | | 수정 시각 | |

#### feed_detail

```
테이블명: feed_detail

Primary Key: post_id (post.post_id와 1:1)

Foreign Key:
	- post_id → post.post_id
	- completion_id → recipe_completion.completion_id (NULL 허용)
	- recipe_id → recipe.recipe_id (NULL 허용)

설계 목적:
	- 피드 글 종류(자랑 / 레시피 공유)와 서비스 데이터(요리 완료, 레시피)를 연결

적재 규칙:
	- feed_type = brag: 사진 1장 이상 필수, completion_id 선택 연결
	  (연결 시 recipe_id는 완료한 레시피로 자동 설정, 화면에 "임박 재료 N개 · N원어치 소진" 표시)
	- feed_type = recipe: 사용자가 작성한 레시피(recipe.source = user)를 recipe_id로 필수 연결
	- 레시피 공유 게시글이 삭제되면 연결된 사용자 레시피는 is_active = FALSE
	- 피드 화면에서는 feed_type으로 탭(전체 / 자랑 / 레시피)을 구분
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **post_id** | BIGINT | N | PK, FK | 게시글 | |
| **feed_type** | VARCHAR(10) | N | | 글 종류 | brag / recipe |
| **completion_id** | BIGINT | Y | FK | 연결된 요리 완료 기록 | brag 선택 |
| **recipe_id** | BIGINT | Y | FK | 연결된 레시피 | recipe 필수 |

#### share_detail

```
테이블명: share_detail

Primary Key: post_id (post.post_id와 1:1)

Foreign Key:
	- post_id → post.post_id
	- region_code → region.region_code
	- item_id → inventory_item.item_id (NULL 허용)

Indexes:
	- idx_share_region_status (region_code, trade_status): 지역·거래 상태별 목록 조회용

설계 목적:
	- 나눔·교환 게시판 전용 정보(제목, 지역, 거래 상태)와 내 재고를 연결

적재 규칙:
	- region_code 기본값은 작성자의 활동 지역
	- 재고 목록에서 나눔 글을 등록하면 item_id를 연결
	- trade_status 흐름: open(나눔중) ↔ reserved(예약중) → done(완료), 완료 전에는 되돌릴 수 있고 완료 후에는 바꿀 수 없음
	- done으로 변경되면 연결된 재고에 inventory_event(shared)를 생성하고 status = shared로 변경, 점수 반영
	- 1:1 채팅, 위치 인증, 거래 후기는 확장 범위
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **post_id** | BIGINT | N | PK, FK | 게시글 | |
| **title** | VARCHAR(50) | N | | 제목 | |
| **share_type** | VARCHAR(10) | N | | 거래 방식 | give(나눔) / exchange(교환) |
| **region_code** | VARCHAR(5) | N | FK | 거래 지역 | |
| **trade_status** | VARCHAR(10) | N | | 거래 상태 | open / reserved / done |
| **item_id** | BIGINT | Y | FK | 연결된 재고 | |
| **done_at** | TIMESTAMPTZ | Y | | 거래 완료 시각 | |

#### post_image

```
테이블명: post_image

Primary Key: image_id

Foreign Key: post_id → post.post_id

Unique: (post_id, sort_order)

적재 규칙:
	- 게시글당 최대 5장 (애플리케이션에서 검증)
	- 이미지는 업로드 API로 먼저 저장하고, 게시글 작성 시 받은 경로만 저장
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **image_id** | BIGSERIAL | N | PK | 이미지 식별자 | |
| **post_id** | BIGINT | N | FK, UQ | 게시글 | |
| **image_path** | VARCHAR(300) | N | | 이미지 경로 | |
| **sort_order** | SMALLINT | N | UQ | 표시 순서 | 1부터 시작 |
| **created_at** | TIMESTAMPTZ | N | | 업로드 시각 | |

#### comment

```
테이블명: comment

Primary Key: comment_id

Foreign Key:
	- post_id → post.post_id
	- author_id → user.id
	- parent_id → comment.comment_id (NULL 허용)

Indexes:
	- idx_comment_post_time (post_id, created_at): 게시글별 댓글 조회용

적재 규칙:
	- 대댓글은 1단계만 허용 (parent_id가 있는 댓글에는 다시 답글을 달 수 없음, 애플리케이션에서 검증)
	- 삭제 시 is_deleted = TRUE로 두고 "삭제된 댓글입니다"로 표시 (대댓글 보존)
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **comment_id** | BIGSERIAL | N | PK | 댓글 식별자 | |
| **post_id** | BIGINT | N | FK | 게시글 | |
| **author_id** | BIGINT | N | FK | 작성자 | |
| **parent_id** | BIGINT | Y | FK | 부모 댓글 | 대댓글일 때 |
| **content** | VARCHAR(500) | N | | 내용 | |
| **is_deleted** | BOOLEAN | N | | 삭제 여부 | 기본값 FALSE |
| **created_at** | TIMESTAMPTZ | N | | 작성 시각 | |
| **updated_at** | TIMESTAMPTZ | N | | 수정 시각 | |

#### post_reaction

```
테이블명: post_reaction

Primary Key: reaction_id

Foreign Key:
	- post_id → post.post_id
	- user_id → user.id

Unique: (post_id, user_id)

적재 규칙:
	- 게시판에 따라 화면 표시만 다름 (feed: 좋아요 / share: 관심)
	- 같은 API로 추가·취소를 토글하며, 취소 시 행을 삭제 (반응은 이력 분석 대상이 아니므로 예외적으로 물리 삭제)
	- 댓글 반응은 범위에서 제외
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **reaction_id** | BIGSERIAL | N | PK | 반응 식별자 | |
| **post_id** | BIGINT | N | FK, UQ | 게시글 | |
| **user_id** | BIGINT | N | FK, UQ | 반응한 사용자 | |
| **created_at** | TIMESTAMPTZ | N | | 반응 시각 | |

#### follow

```
테이블명: follow

Primary Key: follow_id

Foreign Key:
	- follower_id → user.id
	- following_id → user.id

Unique: (follower_id, following_id)

적재 규칙:
	- 자기 자신은 팔로우할 수 없음 (CHECK follower_id <> following_id)
	- 같은 API로 팔로우·언팔로우를 토글하며, 언팔로우 시 행을 삭제
	- 비공개 계정도 MVP에서는 승인 없이 팔로우 가능 (팔로우 요청·승인은 확장 범위)
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **follow_id** | BIGSERIAL | N | PK | 팔로우 식별자 | |
| **follower_id** | BIGINT | N | FK, UQ | 팔로우하는 사용자 | |
| **following_id** | BIGINT | N | FK, UQ | 팔로우 대상 | |
| **created_at** | TIMESTAMPTZ | N | | 팔로우 시각 | |

---

## 8. 점수 데이터

```
점수 데이터는 주간 냉장고 관리 점수와 뱃지를 관리하는 영역입니다.

점수 변화는 재고 이벤트·나눔 완료·배치 감점이 발생할 때 score_event에 사유와 함께 기록하고,
같은 트랜잭션에서 weekly_score의 현재 점수를 갱신하여 홈 화면 게이지에 즉시 반영합니다.

점수 규칙과 뱃지 조건의 값은 테이블로 관리하여 Django Admin에서 조정하고,
판정 로직은 코드로 구현합니다. 초기 값은 시드 데이터로 적재합니다.
규칙 값을 바꿔도 과거 점수는 score_event에 기록된 값 그대로 유지됩니다.
```

### 점수 데이터 테이블 목록

| 테이블명 | 설명 |
| :--- | --- |
| score_rule | 점수 규칙 (가감 점수, 조건 값, 하루 상한) |
| score_event | 점수 변화 기록 |
| weekly_score | 사용자 × 주 점수 |
| badge | 뱃지 정의 |
| user_badge | 뱃지 획득 기록 |

### 점수 데이터 테이블 명세

#### score_rule

```
테이블명: score_rule

Primary Key: rule_id

Unique: code

설계 목적:
	- 점수 규칙의 값(점수, 조건, 상한)을 코드 수정 없이 조정

초기 규칙 (규칙별 점수·공식은 데이터 준비 단계에서 정하고, 테스트 후 조정):
	- expiring_used: 임박 재료(남은 일수 ≤ 3일) 소진, 남은 일수가 적을수록 가중
	- used_up: 재료 다 씀 (임박이 아닌 재료, 요리 완료로 남은 수량이 0이 된 경우 포함)
	- shared_done: 나눔 완료
	- discarded: 폐기 (폐기 금액 비례 감점, 가격 미입력 재료는 기본 감점)
	- neglected: 기한 경과 후 미확인 방치 (일 단위 감점, 재료 1건당 최대 3일)
	- 공통: 하루 가점 상한 (예: +20점)
	- 남은 양 수정(adjusted), 보관 위치 변경·소분에는 점수 없음
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **rule_id** | BIGSERIAL | N | PK | 규칙 식별자 | |
| **code** | VARCHAR(30) | N | UQ | 규칙 코드 | 코드의 판정 로직과 연결 |
| **name** | VARCHAR(50) | N | | 규칙 이름 | 화면 표시용 |
| **points** | SMALLINT | N | | 기본 점수 | 감점은 음수 |
| **params** | JSONB | N | | 조건 값 | 예: {"max_days_left": 3, "max_days": 3} |
| **daily_cap** | SMALLINT | Y | | 하루 상한 | |
| **is_active** | BOOLEAN | N | | 사용 여부 | |
| **updated_at** | TIMESTAMPTZ | N | | 수정 시각 | |

#### score_event

```
테이블명: score_event

Primary Key: score_event_id

Foreign Key:
	- user_id → user.id
	- rule_id → score_rule.rule_id
	- inventory_event_id → inventory_event.event_id (NULL 허용)
	- post_id → post.post_id (NULL 허용)
	- reverted_score_event_id → score_event.score_event_id (NULL 허용)

그레인(1행 정의): 1 row = 점수 변화 1회

Indexes:
	- idx_score_event_user_week (user_id, week_start, created_at): 주간 점수 추이·검증용

설계 목적:
	- 점수가 언제, 얼마나, 왜 바뀌었는지 기록하여 즉시 피드백("+5점 · 임박 재료 2개 소진")과 요일별 추이 그래프에 사용
	- 규칙 변경이나 재계산이 필요할 때 근거 데이터로 사용

적재 규칙:
	- 출처에 따라 연결 컬럼을 채움 (재고 이벤트: inventory_event_id / 나눔 완료: post_id / 방치 감점 배치: 둘 다 NULL)
	- week_start는 이벤트 발생 시각(한국 시간)이 속한 주의 월요일
	- delta는 규칙 적용 후 실제 반영된 점수 (하루 상한으로 잘린 경우 잘린 값)
	- 재고 이벤트가 reverted로 취소되면 반대 부호의 score_event를 생성하고 reverted_score_event_id로 연결
	- 행은 수정·삭제하지 않음
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **score_event_id** | BIGSERIAL | N | PK | 점수 이벤트 식별자 | |
| **user_id** | BIGINT | N | FK | 사용자 | |
| **week_start** | DATE | N | | 해당 주 (월요일) | |
| **rule_id** | BIGINT | N | FK | 적용 규칙 | |
| **delta** | SMALLINT | N | | 가감 점수 | |
| **reason_text** | VARCHAR(100) | N | | 표시 사유 | 예: 임박 재료 2개 소진 |
| **inventory_event_id** | BIGINT | Y | FK | 출처 재고 이벤트 | |
| **post_id** | BIGINT | Y | FK | 출처 나눔 게시글 | |
| **reverted_score_event_id** | BIGINT | Y | FK | 취소 대상 점수 이벤트 | |
| **created_at** | TIMESTAMPTZ | N | | 발생 시각 | |

#### weekly_score

```
테이블명: weekly_score

Primary Key: weekly_score_id

Foreign Key: user_id → user.id

Unique: (user_id, week_start)

설계 목적:
	- 홈 화면 게이지와 프로필에 표시할 이번 주 점수를 빠르게 조회
	- 주간 확정 점수를 보존하여 연속 달성 뱃지와 주간 리포트에 사용

적재 규칙:
	- 사용자의 그 주 첫 점수 이벤트에서 생성 (base_score = 50, 활동 없는 사용자의 빈 행은 만들지 않음)
	- current_score = base_score + 그 주 score_event.delta 합계 (점수 이벤트 저장과 같은 트랜잭션에서 갱신)
	- DB에는 실제 합계를 저장하고, 화면 게이지는 0~100으로 잘라서 표시 (100 초과 시 "만점 달성" 표시)
	- 매주 월요일 배치에서 지난주 행을 확정(is_finalized = TRUE, final_score 기록)하고 뱃지 조건을 판정
	- 이벤트 합계와 current_score의 일치 여부는 검증용 View로 확인
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **weekly_score_id** | BIGSERIAL | N | PK | 주간 점수 식별자 | |
| **user_id** | BIGINT | N | FK, UQ | 사용자 | |
| **week_start** | DATE | N | UQ | 주 시작일 (월요일) | |
| **base_score** | SMALLINT | N | | 기본 점수 | 기본값 50 |
| **current_score** | INT | N | | 현재 점수 | |
| **is_finalized** | BOOLEAN | N | | 확정 여부 | 기본값 FALSE |
| **final_score** | INT | Y | | 확정 점수 | |
| **finalized_at** | TIMESTAMPTZ | Y | | 확정 시각 | |
| **updated_at** | TIMESTAMPTZ | N | | 수정 시각 | |

#### badge

```
테이블명: badge

Primary Key: badge_id

Unique: code

초기 뱃지 (시드 데이터):
	- weekly_zero_waste: 이번 주 폐기 0원 (주간)
	- weekly_all_expiring_used: 임박 재료 모두 소진 (주간)
	- streak_80_3weeks: 3주 연속 점수 80점 이상 (연속)
	- first_capture: 첫 캡처 등록 (첫 달성)
	- first_share: 첫 나눔 완료 (첫 달성)
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **badge_id** | BIGSERIAL | N | PK | 뱃지 식별자 | |
| **code** | VARCHAR(30) | N | UQ | 뱃지 코드 | 코드의 판정 로직과 연결 |
| **name** | VARCHAR(50) | N | | 뱃지 이름 | |
| **description** | VARCHAR(200) | N | | 획득 조건 설명 | |
| **icon** | VARCHAR(100) | Y | | 아이콘 경로 또는 키 | |
| **badge_type** | VARCHAR(10) | N | | 종류 | weekly / streak / first |
| **params** | JSONB | N | | 조건 값 | 예: {"min_score": 80, "weeks": 3} |
| **is_active** | BOOLEAN | N | | 사용 여부 | |

#### user_badge

```
테이블명: user_badge

Primary Key: user_badge_id

Foreign Key:
	- user_id → user.id
	- badge_id → badge.badge_id

Unique:
	- (user_id, badge_id, week_start) — 주간·연속 뱃지는 주마다 다시 획득 가능
	- (user_id, badge_id) WHERE week_start IS NULL — 첫 달성 뱃지는 1회만 (부분 유니크 인덱스)

적재 규칙:
	- 주간·연속 뱃지는 월요일 배치에서 판정, 첫 달성 뱃지는 해당 이벤트 발생 시 즉시 판정
	- 프로필에는 뱃지별 획득 횟수로 표시 (예: 폐기 0원 주간 ×3)
	- 획득 시 notification(badge_earned) 생성
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **user_badge_id** | BIGSERIAL | N | PK | 획득 식별자 | |
| **user_id** | BIGINT | N | FK, UQ | 사용자 | |
| **badge_id** | BIGINT | N | FK, UQ | 뱃지 | |
| **week_start** | DATE | Y | UQ | 획득 주 | 첫 달성 뱃지는 NULL |
| **earned_at** | TIMESTAMPTZ | N | | 획득 시각 | |

---

## 9. 알림 데이터

```
알림 데이터는 서비스 내 알림을 저장하는 영역입니다.

알림은 프론트엔드가 페이지 이동 시와 30초마다 안 읽은 개수를 조회하는
폴링 방식으로 전달합니다. 실시간 전달(웹소켓)은 나눔 1:1 채팅과 함께 확장 범위로 둡니다.

내 행동에 대한 즉시 피드백(점수 변화 등)은 알림이 아니라 해당 API 응답으로 전달하며,
접속 시 표시하는 "오늘의 냉장고" 카드도 알림이 아닌 recommendation_request(trigger = welcome)로 관리합니다.
```

### 알림 데이터 테이블 목록

| 테이블명 | 설명 |
| :--- | --- |
| notification | 서비스 내 알림 |

### 알림 데이터 테이블 명세

#### notification

```
테이블명: notification

Primary Key: notification_id

Foreign Key:
	- recipient_id → user.id
	- actor_id → user.id (NULL 허용)

Unique: dedup_key (NULL 허용)

Indexes:
	- idx_notification_recipient (recipient_id, is_read, created_at): 안 읽은 개수·목록 조회용

설계 목적:
	- 재고·커뮤니티·점수 알림을 하나의 테이블로 관리하고, 클릭 시 이동할 대상을 함께 저장

적재 규칙:
	- notif_type
		· 재고: expiring_summary(하루 1회 오전 9시 요약), expiry_check("아직 있나요?")
		· 커뮤니티: comment, reply, reaction, follow, trade_status
		· 점수: badge_earned, weekly_report
	- 임박 알림은 재료별로 만들지 않고 하루 1건으로 요약 (예: "오늘 임박 재료 3개 · 우유, 두부, 대파")
	- 커뮤니티 알림은 dedup_key = {notif_type}:{actor_id}:{target_id}로 같은 사람 × 같은 대상 × 같은 종류는 1회만 생성
	- 자기 자신의 행동에는 알림을 만들지 않음
	- 데이터는 삭제하지 않고, 알림 목록에는 최근 30일만 표시
	- 알림 종류별 끄기 설정, "○○님 외 N명" 묶음 표시는 확장 범위
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **notification_id** | BIGSERIAL | N | PK | 알림 식별자 | |
| **recipient_id** | BIGINT | N | FK | 받는 사용자 | |
| **notif_type** | VARCHAR(20) | N | | 알림 종류 | 적재 규칙 참고 |
| **actor_id** | BIGINT | Y | FK | 행동한 사용자 | 시스템 알림은 NULL |
| **target_type** | VARCHAR(20) | Y | | 이동 대상 종류 | post, comment, inventory, badge, report 등 |
| **target_id** | BIGINT | Y | | 이동 대상 식별자 | |
| **message** | VARCHAR(200) | N | | 표시 문구 | |
| **dedup_key** | VARCHAR(100) | Y | UQ | 중복 방지 키 | 커뮤니티 알림 |
| **is_read** | BOOLEAN | N | | 읽음 여부 | 기본값 FALSE |
| **read_at** | TIMESTAMPTZ | Y | | 읽은 시각 | |
| **created_at** | TIMESTAMPTZ | N | | 생성 시각 | |

---

## 10. 리포트 View

```
리포트 View는 오늘의 변화, 주간 리포트, 월간 가계부, 재료별 활용률의 계산 기준을 고정하기 위한 영역입니다.

모든 금액 집계는 재고 등록 시점의 purchase_price와
이벤트 발생 시점에 저장된 value_delta만을 사용하여,
이후 수량이나 가격을 수정하더라도 과거 리포트 값이 바뀌지 않도록 합니다.
집계 기준일은 구매 금액은 구매일(purchase_date), 소비·폐기·나눔은 이벤트 발생일(한국 시간)입니다.
reverted 이벤트와 남은 양을 늘린 adjusted 이벤트는 음수로 기록되므로 합계에 그대로 포함하면 반영됩니다.
소분(split)은 두 건의 가격 합이 원래 가격과 같아 구매 금액 집계가 바뀌지 않습니다.
```

### 리포트 View 목록

| View명 | 설명 | 그레인 |
| :--- | --- | --- |
| vw_daily_summary | 오늘의 변화 | 사용자 × 일 |
| vw_weekly_report | 주간 리포트 | 사용자 × 주 |
| vw_monthly_ledger | 월간 가계부 (보조) | 사용자 × 월 |
| vw_ingredient_utilization | 재료별 활용률·폐기율 | 사용자 × 표준 재료 (최근 90일) |
| vw_weekly_score_check | 주간 점수 검증 | 사용자 × 주 |

### 리포트 View 명세

#### vw_daily_summary

```
설계 목적:
	- 홈 화면 "오늘의 변화"(오늘 아낀 금액, 버린 금액, 점수 변화) 표시

계산 기준:
	- source: inventory_event, inventory_item, score_event
	- used_value = SUM(value_delta) WHERE event_type IN ('consumed', 'used_up', 'adjusted') (취소·늘리기 포함)
	- expiring_used_value = 위 조건 중 days_left ≤ 3인 이벤트의 value_delta 합계
	- wasted_value = SUM(value_delta) WHERE event_type = 'discarded' (취소 포함)
	- shared_value = SUM(value_delta) WHERE event_type = 'shared'
	- score_delta = 해당 일 score_event.delta 합계
	- 하루 합계가 음수로 계산되면(예: 어제 쓴 양을 오늘 늘림) View에는 그대로 두고 API 응답에서 0으로 표시
```

| 컬럼명 | 설명 |
| :--- | --- |
| **user_id** | 사용자 |
| **summary_date** | 날짜 (한국 시간) |
| **used_value** | 소진 금액 |
| **expiring_used_value** | 임박 재료 소진 금액 |
| **wasted_value** | 폐기 금액 |
| **shared_value** | 나눔 금액 |
| **score_delta** | 점수 변화 합계 |

#### vw_weekly_report

```
설계 목적:
	- 주간 리포트(구매·소진·폐기·나눔 금액, 자주 버린 재료, 지난주 대비)와 요일별 점수 추이 제공

계산 기준:
	- source: inventory_item, capture, inventory_event, weekly_score
	- item_spend = SUM(inventory_item.purchase_price) (구매일이 해당 주인 재고)
	- order_discount, delivery_fee = 확정된 capture의 해당 주 합계
	- used_value, wasted_value, shared_value = vw_daily_summary의 주간 합계
	- waste_rate = wasted_value / (used_value + wasted_value + shared_value)
	- top_wasted = 폐기 금액 상위 3개 재료 (JSONB)
	- prev_* = 직전 주 값 (LAG)
	- final_score = weekly_score.final_score (확정 전이면 current_score)
```

| 컬럼명 | 설명 |
| :--- | --- |
| **user_id** | 사용자 |
| **week_start** | 주 시작일 (월요일) |
| **item_spend** | 품목 구매 금액 |
| **order_discount** | 주문 할인 |
| **delivery_fee** | 배송비 |
| **used_value** | 소진 금액 |
| **wasted_value** | 폐기 금액 |
| **shared_value** | 나눔 금액 |
| **waste_rate** | 폐기 비율 |
| **top_wasted** | 폐기 금액 상위 재료 |
| **prev_wasted_value** | 지난주 폐기 금액 |
| **prev_item_spend** | 지난주 구매 금액 |
| **final_score** | 주간 점수 |

#### vw_monthly_ledger

```
설계 목적:
	- 가계부 형태의 월별 식비·폐기 금액 보조 제공

계산 기준:
	- source: inventory_item, capture, inventory_event
	- item_spend = SUM(inventory_item.purchase_price) (구매일 기준 월)
	- order_discount = SUM(capture.order_discount_amount) (확정된 캡처, 구매일 기준 월)
	- delivery_fee = SUM(capture.delivery_fee)
	- net_spend = item_spend - order_discount + delivery_fee
	- wasted_value = 해당 월 discarded 이벤트의 value_delta 합계
	- purchase_price가 NULL인 재고는 item_spend에서 제외하고 missing_price_cnt로 별도 표시
	- purchase_cnt는 소분으로 생긴 건(parent_item_id가 있는 건)을 제외하고 셈
```

| 컬럼명 | 설명 |
| :--- | --- |
| **user_id** | 사용자 |
| **year_month** | 연-월 (YYYY-MM) |
| **item_spend** | 품목 구매 금액 합계 |
| **order_discount** | 주문 단위 할인 합계 |
| **delivery_fee** | 배송비 합계 |
| **net_spend** | 실 지출 식비 |
| **wasted_value** | 폐기 금액 |
| **purchase_cnt** | 구매 품목 수 |
| **missing_price_cnt** | 가격 미입력 품목 수 |

#### vw_ingredient_utilization

```
설계 목적:
	- 재료별로 산 만큼 쓰고 있는지 확인하여 주간 리포트의 "자주 버리는 재료"와 구매량 조정 대상을 식별

계산 기준:
	- source: inventory_item, inventory_event (최근 90일 내 구매한 재고)
	- bought_value = SUM(purchase_price)
	- utilization_rate = (소진 금액 + 나눔 금액) / 구매 금액
	- waste_rate = 폐기 금액 / 구매 금액
	- avg_days_to_use_up = 구매일 → used_up 상태가 된 시점까지 평균 일수
	- purchase_cnt는 소분으로 생긴 건을 제외하고 셈
```

| 컬럼명 | 설명 |
| :--- | --- |
| **user_id** | 사용자 |
| **ingredient_id** | 표준 재료 |
| **purchase_cnt** | 구매 횟수 |
| **bought_value** | 구매 금액 |
| **utilization_rate** | 활용률 |
| **waste_rate** | 폐기율 |
| **avg_days_to_use_up** | 평균 소진 소요일 |

#### vw_weekly_score_check

```
설계 목적:
	- weekly_score.current_score에 캐시한 값이 score_event 합계와 일치하는지 검증

계산 기준:
	- source: weekly_score, score_event
	- event_sum = base_score + SUM(score_event.delta) (같은 사용자·주)
	- is_consistent = (event_sum = current_score)
```

| 컬럼명 | 설명 |
| :--- | --- |
| **user_id** | 사용자 |
| **week_start** | 주 시작일 |
| **current_score** | 캐시된 현재 점수 |
| **event_sum** | 이벤트 기준 점수 |
| **is_consistent** | 일치 여부 |

---

## 11. 테이블 관계 요약

```
region ─< user ─┬─< capture ─< capture_item ── inventory_item
                │                                   │
                ├─< inventory_item ─< inventory_event ─────────┐
                │        │  └─(parent_item_id: 소분)          │
                │        │                └─< score_event >─ score_rule
                │        │                        │
                │        │                  weekly_score
                │        │
ingredient_group ─< ingredient ─< product_alias
       │                 └─< inventory_item
       │
recipe ─< recipe_ingredient
   │
   ├─< recommendation_impression >── recommendation_request ── user
   │            │
   ├─< recipe_completion ─< inventory_event (consumed)
   │            │
   └──── feed_detail ── post ─┬─ share_detail ── inventory_item
                              ├─< post_image
                              ├─< comment
                              └─< post_reaction

user ─< follow >─ user
user ─< user_badge >─ badge
user ─< notification

(─< : 1 대 N 관계)
```

- **재료 매칭 경로**: inventory_item → ingredient → ingredient_group ← recipe_ingredient
- **비회원 매칭 경로**: 고른 ingredient_group → recipe_ingredient(group_id) → recipe (기록 없음)
- **RAG 추천 경로**: inventory_item(임박) → recommendation_request(input_snapshot, candidates ← recipe.embedding) → recommendation_impression
- **재고 차감 경로**: recipe_completion → (사용자 사용량 선택) → inventory_item(소비기한 빠른 순) → inventory_event(consumed, value_delta)
- **소분 경로**: inventory_item(원래 건) → inventory_event(split) → inventory_item(새 건, parent_item_id)
- **점수 경로**: inventory_event / share_detail(done) / 방치 배치 → score_event(score_rule 적용) → weekly_score → user_badge
- **나눔 경로**: inventory_item → share_detail(item_id) → done → inventory_event(shared)
- **피드 연결 경로**: recipe_completion → feed_detail(brag) / recipe(source = user) → feed_detail(recipe)
- **인식 평가 경로**: capture_item의 predicted_* ↔ confirmed_* 비교
- **추천 평가 경로**: recommendation_request(candidates, status) + recommendation_impression(is_clicked) + recipe_completion
- **금액 집계 경로**: inventory_item.purchase_price(식비) / inventory_event.value_delta(소비·폐기·나눔) → 리포트 View

---

## 부록. 확장 시 추가 테이블

```
아래 테이블은 MVP 범위에서 제외하고, 확장 기능을 구현할 때 추가합니다.
소진 플래너, 부족 재료 안내, 단위 변환은 이미 설계한 내용을 보존하고,
나머지는 추가 방향만 기록합니다.
```

### A. 소진 플래너

#### meal_plan

```
테이블명: meal_plan

Primary Key: plan_id

Foreign Key: user_id → user.id

Unique: (user_id, week_start_date, version)

설계 목적:
	- 사용자별 주간 소진 계획의 기준 기간과 기대 효과를 저장
	- 계획 생성 방식(strategy)을 기록하여 탐욕 알고리즘과 최적화 모델의 성과를 비교

적재 규칙:
	- week_start_date는 계획 주의 월요일
	- 새 재료 등록 등으로 계획을 다시 생성하면 version을 증가시키고 이전 계획은 status = replaced로 변경
	- target_value: 계획 기간 내 소비기한이 도래하는 재고의 남은 가치 합계 (계획 생성 시점 스냅샷)
	- planned_saved_value: 계획의 레시피를 모두 완료할 경우 소진되는 임박 재고 가치 합계
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **plan_id** | BIGSERIAL | N | PK | 계획 식별자 | |
| **user_id** | BIGINT | N | FK, UQ | 사용자 | |
| **week_start_date** | DATE | N | UQ | 계획 시작일 (월요일) | |
| **version** | SMALLINT | N | UQ | 계획 버전 | 재생성 시 증가 |
| **strategy** | VARCHAR(20) | N | | 계획 생성 방식 | greedy_v1 / ilp_v1 등 |
| **target_value** | INT | N | | 기간 내 임박 재고 가치 (원) | 생성 시점 스냅샷 |
| **planned_saved_value** | INT | N | | 계획상 소진 예정 가치 (원) | 생성 시점 스냅샷 |
| **status** | VARCHAR(10) | N | | 계획 상태 | active / replaced / closed |
| **created_at** | TIMESTAMPTZ | N | | 생성 시각 | |

#### meal_plan_item

```
테이블명: meal_plan_item

Primary Key: plan_item_id

Foreign Key:
	- plan_id → meal_plan.plan_id
	- recipe_id → recipe.recipe_id

그레인(1행 정의): 1 row = 계획에 포함된 레시피 1개

적재 규칙:
	- target_items에는 이 레시피로 소진될 재고(item_id)와 예상 소진 수량·가치를 JSONB 배열로 저장
	- 사용자가 레시피를 교체하면 기존 행은 status = swapped로 남기고 새 행을 추가
	- 완료 시 recipe_completion에 plan_item_id 컬럼을 추가하여 연결하고 status = done으로 변경
	- 예정일이 지나도 완료되지 않으면 status = skipped (주간 배치에서 갱신)
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **plan_item_id** | BIGSERIAL | N | PK | 계획 항목 식별자 | |
| **plan_id** | BIGINT | N | FK | 계획 | |
| **recipe_id** | BIGINT | N | FK | 레시피 | |
| **planned_date** | DATE | N | | 예정일 | |
| **sequence** | SMALLINT | N | | 계획 내 순서 | |
| **planned_value** | INT | N | | 이 레시피로 소진할 예정 가치 (원) | |
| **target_items** | JSONB | N | | 소진 대상 재고 목록 | [{item_id, quantity, value}] |
| **status** | VARCHAR(10) | N | | 항목 상태 | planned / done / skipped / swapped |
| **created_at** | TIMESTAMPTZ | N | | 생성 시각 | |

#### vw_plan_performance

```
계산 기준:
	- source: meal_plan, meal_plan_item, recipe_completion, inventory_event
	- done_rate = 완료 항목 수 / 계획 항목 수 (swapped 제외)
	- actual_saved_value = 계획 기간 내 target 재고의 consumed 이벤트 value_delta 합계
	- achieved_rate = actual_saved_value / planned_saved_value
```

| 컬럼명 | 설명 |
| :--- | --- |
| **plan_id** | 계획 |
| **user_id** | 사용자 |
| **strategy** | 계획 방식 |
| **target_value** | 기간 내 임박 재고 가치 |
| **planned_saved_value** | 계획상 소진 예정 가치 |
| **actual_saved_value** | 실제 소진 가치 |
| **done_rate** | 계획 이행률 |
| **achieved_rate** | 계획 대비 소진 달성률 |

### B. 부족 재료 안내

#### vw_restock_candidates

```
후보 산출 기준 (reason):
	- plan_needed: 활성 소진 계획의 레시피에 필요하지만 active 재고가 없는 재료 그룹
	- regular_out: 최근 90일 2회 이상 구매하고 utilization_rate ≥ 0.8인 재료 중,
	  active 재고가 없거나 남은 비율이 30% 미만인 재료
	- regular_due: 위 조건의 재료 중 마지막 구매일 + avg_days_to_use_up이 조회 기간 내에 도래하는 재료
	- buy_less: waste_rate ≥ 0.3인 재료 (소용량 구매 권장 표시용)

조회 기간:
	- API 파라미터로 7일(주간) 또는 30일(월간)을 받아 regular_due 판단에 사용
```

| 컬럼명 | 설명 |
| :--- | --- |
| **user_id** | 사용자 |
| **ingredient_id** | 표준 재료 (plan_needed는 그룹의 대표 재료) |
| **group_id** | 재료 그룹 |
| **reason** | 후보 사유 (plan_needed / regular_out / regular_due / buy_less) |
| **expected_date** | 소진 예상일 (regular_due) |
| **related_plan_item_id** | 관련 계획 항목 (plan_needed) |

### C. 레시피 분량 자동 제안

#### unit_conversion

```
테이블명: unit_conversion

Primary Key: conversion_id

Foreign Key: ingredient_id → ingredient.ingredient_id (NULL 허용)

Unique: (from_unit, ingredient_id)

설계 목적:
	- 레시피 분량 텍스트(컵, 큰술, 작은술, 개 등)를 표준 단위로 변환하여
	  완료 확인 화면의 사용량 기본값을 자동 제안

적재 규칙:
	- recipe_ingredient에 amount(NUMERIC), unit 컬럼을 추가하고 LLM으로 분량 텍스트를 일괄 파싱
	- ingredient_id가 NULL이면 모든 재료에 적용되는 공통 변환 (예: 1컵 = 200ml, 1큰술 = 15ml)
	- 재료별 변환이 있으면 공통 변환보다 우선 적용
	- "약간", "적당량" 등 수량화할 수 없는 표기는 변환 대상에서 제외
```

| 컬럼명 | 타입 | NULL | Key | 설명 | 비고 |
| :--- | --- | --- | --- | --- | --- |
| **conversion_id** | BIGSERIAL | N | PK | 변환 식별자 | |
| **from_unit** | VARCHAR(10) | N | UQ | 원본 단위 | 컵, 큰술, 작은술, 개 등 |
| **ingredient_id** | BIGINT | Y | UQ, FK | 적용 재료 | NULL이면 공통 변환 |
| **to_unit** | VARCHAR(5) | N | | 표준 단위 | 개 / g / ml |
| **factor** | NUMERIC(10,2) | N | | 변환 계수 | 1 from_unit = factor to_unit |

### D. 기타 확장 (추가 방향만 기록)

| 기능 | 추가 내용 |
| :--- | --- |
| 소셜 로그인 (카카오 등) | social_account(provider, provider_uid, user_id) 테이블 추가, (provider, provider_uid) 유니크, 가입 직후 닉네임·이메일 입력 단계 |
| 토큰 만료·JWT 전환 | DRF 토큰에 만료 기준 추가 또는 JWT로 전환 (토큰 테이블 대신 블랙리스트 테이블) |
| 레시피 포크 | recipe.parent_recipe_id(NULL 허용 FK) 추가, 상세 화면에 원본 레시피 표시 |
| 사용자 레시피 추천 포함 | 좋아요·완료 수 기준을 정해 recipe.is_recommendable = TRUE로 전환 후 임베딩 |
| 나눔 1:1 채팅 | chat_room(share 게시글 × 참여자), chat_message 테이블 추가, Django Channels + Redis 기반 웹소켓 도입, 알림 전달도 웹소켓으로 전환 |
| 보관·손질 Q&A 게시판 | post.board에 qna 추가, qna_detail(채택 답변 등) 테이블, 전문가 뱃지 |
| 동네 랭킹 | user.region_code × weekly_score 집계 View |
| 알림 설정·묶음 표시 | notification_setting(user × notif_type) 테이블, 반응 알림 묶음 처리 |
| 팔로우 요청·승인 | follow에 status(requested / accepted) 추가 |
| 개인화 랭킹 모델 | recommendation_impression.features + 클릭·완료 라벨로 CatBoost 학습 |
