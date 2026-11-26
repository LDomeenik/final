# 소비기한 API 관련 정리본

> 조사일: 2026-11-27
> 관련 문서: [서비스 기획서](../docs/Service_Plan.md) 4장, [데이터 명세서](../docs/Data_Specification.md) 2장(기준 데이터), [기능 명세서](../docs/Feature_Specification.md) ADM-01

## 요약

- **식재료 단위로 소비기한을 바로 받아 쓸 수 있는 오픈 API는 확인되지 않았다.**
- 기존 결정(소비기한 기준 테이블 직접 구축)을 유지한다.
- 다만 공공 자료 3~4종을 바탕으로 채우면 손으로 처음부터 만들 필요는 없다.
  - 신선식품: **USDA FoodKeeper** (JSON 파일)
  - 가공식품: **식약처 소비기한 참고값** + **식품안전나라 I1250 신고 데이터 통계**
  - 보완: 농촌진흥청 파일데이터 (확인 필요)
  - 빈 곳: LLM 초안 → 사람 검수
- 기준값은 거의 바뀌지 않는 데이터이므로 실시간 API 호출이 아니라 **미리 DB에 적재**하는 방식이 맞다.

---

## 1. 문제 상황

- 결제내역 캡처에는 소비기한 정보가 없다. 그래서 "구매일 + 재료별 기준 일수"로 **예상 소비기한**을 계산해야 한다.
- 이를 위해 표준 재료(100~150개)마다 실온·냉장·냉동·개봉 후 일수가 필요하다.
  - 데이터 명세서의 `room_days`, `fridge_days`, `freezer_days`, `opened_days`
- 이 값을 API로 받아 오려 했으나 마땅한 API가 없다.

## 2. API로 해결이 안 되는 이유 (한계점)

### 2.1 신선식품은 표준 값 자체가 없다
- 채소·과일·고기·생선은 품종, 보관 온도, 구매 시점의 신선도에 따라 기간이 크게 달라진다.
- 신선식품의 남은 소비기한을 정하는 표준 측정 방법이 아직 없다는 지적이 있다 ([ASTM 작업 항목](https://www.astm.org/membership-participation/technical-committees/workitems/workitem-wk95933)).
- 그래서 기관들은 API 대신 "냉장 3~5일" 같은 **안내 수준의 자료**만 낸다.

### 2.2 식약처 소비기한 참고값은 API가 아니다
- 식약처가 실험으로 정한 식품유형별 잠정 소비기한이다. 2023년 보도 기준 51개 유형 550개 품목이 공개됐다.
- 안내서와 웹 검색으로만 제공되고, 오픈 API나 파일데이터로 제공된다는 근거는 찾지 못했다.
- 가공식품 위주라 신선식품은 거의 없다.

### 2.3 식품안전나라 API는 "제품 단위"다
- 소비기한 필드(`POG_DAYCNT`)가 있는 API는 있다 (3장 참고). 다만 다음과 같은 한계가 있다.

| 한계 | 설명 | 우리 서비스에 미치는 영향 |
|---|---|---|
| 제품 단위 | "○○회사 ○○우유 1L"처럼 회사가 신고한 제품별 값 | 결제내역 속 "우유"(재료 단위)와 바로 연결되지 않음 |
| 가공식품만 | 제조 신고 대상만 있음 | 채소·고기·생선은 없음 |
| 형식 불규칙 | "제조일로부터 12개월" 같은 문장으로 들어 있음 | 일수로 바꾸는 정제 필요 |
| 제조일 기준 | 제조일부터 센 기간 | 우리는 구매일 기준이라 그대로 쓰면 실제보다 길게 잡힘 |

### 2.4 해외 API도 맞지 않는다
- 무료로 공개된 신선식품 소비기한 API는 찾지 못했다.
- 있는 것은 센서(온도·습도·가스) 값을 넣어 예측하는 물류용 상용 도구뿐이다.

---

## 3. 조사한 API·자료 목록

| 자료 | 제공 기관 | 형태 | 대상 | 판단 |
|---|---|---|---|---|
| [FoodKeeper Data](https://catalog.data.gov/dataset/fsis-foodkeeper-data) | USDA FSIS (미국 농무부) | JSON·Excel 다운로드 | 신선식품 포함 수백 개 품목 | ✅ **신선식품 기준값의 주 자료** |
| [소비기한 참고값](https://www.mfds.go.kr/brd/m_827/view.do?seq=3616&srchFr=&srchTo=&srchWord=&srchTp=&itm_seq_1=0&itm_seq_2=0&multi_itm_seq=0&company_cd=&company_nm=&page=4) / [식품산업협회 검색](https://www.kfia.or.kr/kfia/sub.php?menukey=1513) | 식약처 / 한국식품산업협회 | 안내서·웹 검색 | 가공식품 51개 유형 550개 품목 (2023년 보도 기준) | ✅ **가공식품 기준값의 주 자료** |
| [I1250 식품(첨가물)품목제조보고](https://www.foodsafetykorea.go.kr/api/openApiInfo.do?menu_grp=MENU_GRP31&menu_no=656&show_cnt=10&start_idx=1&svc_no=I1250&svc_type_cd=API_TYPE06) | 식약처 식품안전나라 | 오픈 API (무료, 인증키) | 신고된 가공식품 제품 | 🔶 통계로 가공해서 보조 자료로 사용 |
| [C005 바코드연계제품정보](https://www.foodsafetykorea.go.kr/api/openApiInfo.do?menu_grp=MENU_GRP31&menu_no=661&show_cnt=10&start_idx=1&svc_no=C005) | 식약처 식품안전나라 | 오픈 API | 바코드가 있는 제품 | 🔶 결제내역에 바코드가 없어 지금은 쓰기 어려움. 포장지 인식(P2) 때 검토 |
| [I0030 건강기능식품 품목제조 신고사항](https://www.foodsafetykorea.go.kr/api/openApiInfo.do?menu_grp=MENU_GRP31&menu_no=661&show_cnt=10&start_idx=1&svc_no=I0030) | 식약처 식품안전나라 | 오픈 API | 건강기능식품 | ❌ 우리 서비스와 무관 |
| 농촌진흥청 "농산물 저장과 가공" ([공공데이터포털](https://www.data.go.kr/data/15059042/openapi.do) 관련 데이터) | 농촌진흥청 | 파일데이터로 표시됨 | 농산물 저장 | ❓ 열어 보고 판단. 저장 일수가 구조화돼 있으면 보완 자료로 사용 |
| [jelera/food-shelflife-db](https://www.github.com/jelera/food-shelflife-db) | 개인 프로젝트 | FoodKeeper를 감싼 비공식 API | FoodKeeper와 같음 | ❌ 안정성 보장 없음. 원본 파일을 직접 받는 게 나음 |
| [WUR Shelf Life Calculator](https://www.freshplaza.com/africa/article/9846719/wur-launches-shelf-life-prediction-tool/) | 네덜란드 바헤닝언대 | API (조건 불명) | 센서 기반 신선식품 예측 | ❌ 물류용, 센서 값이 필요함 |

### 3.1 USDA FoodKeeper 상세
- 라이선스: **CC0** (퍼블릭 도메인). 출처만 표기하면 된다.
- 마지막 수정일: 2025-01-22 (data.gov 기준)
- 영어·스페인어·포르투갈어 버전이 있다.
- 실온·냉장·냉동·개봉 후 보관 기간을 다뤄서 우리 컬럼 구조와 거의 같다. 정확한 컬럼 이름은 [데이터 문서(PDF)](https://www.fsis.usda.gov/sites/default/files/media_file/2020-06/Data-Documentation-FoodKeeper-Application.pdf)로 확인해야 한다.
- 한계
  - 미국 기준이라 김치·두부·깻잎 같은 한국 재료는 빠져 있을 가능성이 크다 (추측, 확인 필요).
  - 값이 "2~3일"처럼 범위로 되어 있다.
  - USDA도 "엄격한 규칙이 아닌 참고용 가이드"라고 밝힌다.

### 3.2 식품안전나라 I1250 상세
- 이용 방법: 레시피 API(COOKRCP01)와 같다. 식품안전나라 회원가입 → 오픈 API 이용신청 → 인증키 발급 (무료).
- 주요 필드: 제품명, 식품유형, `POG_DAYCNT`(소비기한), `QLITY_MNTNC_TMLMT_DAYCNT`(품질유지기한일수)
- 응답 예시에서 소비기한이 "제조일로부터 12개월" 같은 문자열로 온다.

---

## 4. 대체 자료 활용 방안

### 4.1 출처별 역할

| 재료 종류 | 1순위 | 2순위 | 3순위 |
|---|---|---|---|
| 가공식품 (우유, 두부, 햄 등) | 식약처 참고값 | I1250 유형별 통계 | FoodKeeper |
| 신선식품 (채소, 과일, 고기, 생선) | FoodKeeper | 농촌진흥청 자료 (쓸 수 있으면) | LLM 초안 |
| 한국 특유 재료 (김치, 깻잎 등) | 식약처 참고값 (있으면) | LLM 초안 | - |

- 같은 재료가 여러 자료에 있으면 **한국 기준인 식약처 값을 우선**한다.
- 모든 값은 사람이 검수한 뒤 적재한다.

### 4.2 구축 절차 (ADM-01 "LLM 초안 → 사람 검수 → 적재"와 연결)

1. **원본 수집**
   - FoodKeeper JSON 다운로드 (영어 원본)
   - 식약처 참고값 중 표준 재료에 해당하는 품목만 표로 옮기기
   - I1250 인증키 발급 후 데이터 수집
2. **I1250 통계 만들기**
   - `POG_DAYCNT` 문자열을 일수로 변환 ("12개월" → 365일 등)
   - 식품유형별로 모아 **하위 25% 값**을 기준으로 사용 (짧은 쪽을 택해 안전하게)
   - 참고: 같은 방식을 쓴 공개 프로젝트 [vium-BSSM/vium_BE #87](https://github.com/vium-BSSM/vium_BE/issues/87)
3. **표준 재료와 매칭**
   - LLM으로 우리 표준 재료 ↔ FoodKeeper 항목 / 식약처 유형을 대응
   - 대응할 항목이 없는 재료는 LLM이 일수 초안 작성
4. **값 확정 규칙**
   - 범위 값("3~5일")은 **짧은 쪽**을 사용한다. 버리는 것보다 일찍 알려 주는 편이 낫다.
   - 제조일 기준 값은 유통 기간을 고려해 줄여서 쓴다. 얼마나 줄일지는 팀에서 정한다.
5. **검수·적재**
   - 사람이 검수한 뒤 `ingredient` 테이블에 적재한다.
   - 출처는 `expiry_basis`로 기록한다.
6. **운영 중 보정**
   - "아직 있나요?" 응답과 실제 소진·폐기 시점을 쌓아 기준값을 고친다 (`expiry_basis = adjusted`).

### 4.3 `expiry_basis` 값 정리 (팀 결정 필요)

| 값 | 의미 | 상태 |
|---|---|---|
| `mfds_ref` | 식약처 참고값 | 데이터 명세서에 있음 |
| `general` | 일반 보관 기준 | 데이터 명세서에 있음 |
| `adjusted` | 사용 이력으로 보정 | 데이터 명세서에 있음 |
| `usda` | FoodKeeper 값 | **추가 검토**: `general`에 포함할지, 따로 둘지 |
| `mfds_stat` | I1250 유형별 통계 값 | **추가 검토** |
| `llm` | LLM 초안 후 검수 | **추가 검토** |

- 출처를 나눠 두면 나중에 "어느 출처 값이 실제와 많이 틀렸는지" 분석할 수 있다.

---

## 5. 포트폴리오·발표에서 설명할 포인트

- **문제**: 식재료 소비기한을 제공하는 API가 없음
- **조사**: 국내(식약처, 농촌진흥청)와 해외(USDA, 상용 도구) 자료를 비교하고, 제품 단위·재료 단위 차이를 확인
- **해결**: 공공 자료 여러 개를 출처별 우선순위로 합쳐 기준 테이블을 직접 구축하고, 출처(`expiry_basis`)를 기록
- **개선**: 실제 사용 이력으로 기준값을 보정하는 구조 (`adjusted`)

---

## 6. 남은 확인 사항

- [ ] FoodKeeper JSON을 내려받아 항목 수와 컬럼 구조 확인, 표준 재료와 얼마나 겹치는지 확인
- [ ] 식품안전나라 인증키 발급 후 I1250 샘플 호출, `POG_DAYCNT` 형식과 식품유형 필드 확인
- [ ] COOKRCP01 인증키를 I1250에도 쓸 수 있는지 확인 (같은 키로 될 것으로 추측)
- [ ] 농촌진흥청 "농산물 저장과 가공" 파일을 받아 저장 일수가 구조화돼 있는지 확인
- [ ] 공공데이터포털(data.go.kr)에서 "소비기한"으로 직접 검색 (이번 조사에서 하지 못함)
- [ ] `expiry_basis` 값 추가 여부를 팀에서 결정하고 데이터 명세서에 반영

---

## 참고 자료

- [FSIS FoodKeeper Data (data.gov)](https://catalog.data.gov/dataset/fsis-foodkeeper-data)
- [FoodKeeper 데이터 문서 (USDA FSIS, PDF)](https://www.fsis.usda.gov/sites/default/files/media_file/2020-06/Data-Documentation-FoodKeeper-Application.pdf)
- [식약처: 대표적인 식품들의 소비기한 참고값](https://www.mfds.go.kr/brd/m_827/view.do?seq=3616&srchFr=&srchTo=&srchWord=&srchTp=&itm_seq_1=0&itm_seq_2=0&multi_itm_seq=0&company_cd=&company_nm=&page=4)
- [의학신문: 39개 식품유형 소비기한 참고값 공개](http://www.bosa.co.kr/news/articleView.html?idxno=2202704)
- [한국식품산업협회 소비기한 참고값](https://www.kfia.or.kr/kfia/sub.php?menukey=1513)
- [식품안전나라 I1250 식품(첨가물)품목제조보고](https://www.foodsafetykorea.go.kr/api/openApiInfo.do?menu_grp=MENU_GRP31&menu_no=656&show_cnt=10&start_idx=1&svc_no=I1250&svc_type_cd=API_TYPE06)
- [식품안전나라 C005 바코드연계제품정보](https://www.foodsafetykorea.go.kr/api/openApiInfo.do?menu_grp=MENU_GRP31&menu_no=661&show_cnt=10&start_idx=1&svc_no=C005)
- [식품안전나라 I0030 건강기능식품 품목제조 신고사항](https://www.foodsafetykorea.go.kr/api/openApiInfo.do?menu_grp=MENU_GRP31&menu_no=661&show_cnt=10&start_idx=1&svc_no=I0030)
- [식의약 데이터 포털](https://data.mfds.go.kr/)
- [공공데이터포털 농촌진흥청 관련 데이터](https://www.data.go.kr/data/15059042/openapi.do)
- [vium-BSSM/vium_BE #87: 공공데이터 기반 소비기한 규칙 시드](https://github.com/vium-BSSM/vium_BE/issues/87)
- [jelera/food-shelflife-db](https://www.github.com/jelera/food-shelflife-db)
- [WUR shelf life prediction tool (FreshPlaza)](https://www.freshplaza.com/africa/article/9846719/wur-launches-shelf-life-prediction-tool/)
- [ASTM 남은 소비기한 측정 방법 작업 항목](https://www.astm.org/membership-participation/technical-committees/workitems/workitem-wk95933)
