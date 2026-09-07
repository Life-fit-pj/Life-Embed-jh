# LIFE,FIT — 추천 엔진

서울 427개 행정동 중 사용자의 자연어 검색어에 맞는 동네 TOP 5를 고르고,
LLM이 근거를 들어 설명해 주는 파이프라인입니다.

화면과 서버는 [life-fit-web](https://github.com/easty00/life-fit-web)에 있습니다.

---

## 무엇을 하는가

```
"애들 학원 보내기 좋은 곳"
    ↓  weights.py      검색어 → 7개 지표 가중치
       교육 4.6 / 나머지 2.6~3.3
    ↓  (housing.py)    건물유형·거래유형·예산이 검색어에 있으면 그 조건에 맞는 동으로 먼저 추림
    ↓  recommend.py    가중치 → TOP 5
       방이1동 · 중계1동 · 쌍문제4동 · 대치1동 · 염리동
    ↓  explain.py      결과 → 사람이 읽을 설명문 (시세·조건 일치도 포함)
```

기존 서비스가 "3인 가구 40대"처럼 인구통계로 나누는 것과 달리,
**라이프스타일 선호도**로 동네를 고릅니다.

추천을 받은 뒤에는 지도 핀 하나를 설명하거나(`region_explain.py`),
후속 질문에 답하는(`chat.py`) 두 가지 창구가 더 있습니다.

---

## 설치

### 1. 패키지

```bash
py -m pip install -r requirements.txt
```

버전이 고정돼 있습니다 — numpy 2.5.1 · python-dotenv 1.2.2 · langchain-anthropic 1.6.1 ·
langchain-huggingface 1.2.2 · sentence-transformers 5.7.0.

빌드·린트 도구를 정의하는 매니페스트(`pyproject.toml` 등)는 아직 없습니다.
테스트는 `tests/`에 있습니다 — `py -m pytest tests -q` (아래 "확인하는 법" 참고).

### 2. API 키

프로젝트 루트에 `.env` 파일을 만듭니다.

```
ANTHROPIC_API_KEY=sk-ant-...
```

없으면 `app/core/config.py`가 import 시점에 `RuntimeError`를 냅니다.
`.env`는 절대 깃에 올리지 마세요.

쓰는 모델도 `config.py`에 있습니다 — 설명문 LLM은 `claude-haiku-4-5-20251001`(`MODEL`),
임베딩은 `intfloat/multilingual-e5-small`(`EMBED_MODEL`, 384차원).

> 서버 쪽 관리자 토큰(`ADMIN_TOKEN`, `ADMIN_WRITE_ENABLED`)은 여기가 아니라
> 이웃 저장소 `Life-Web`의 `.env`에 있습니다. 두 파일은 용도가 다릅니다.

### 3. DB 준비

`data/life.db`(약 73MB)는 깃에 첨부되어있으나, 용량문제가 생기면 삭제 예정입니다. 삭제되어 존재하지 않을 경우 아래의 방안 둘 중 하나를 선택하세요.

Git LFS로 관리되므로, 체크아웃 직후 이 파일이 133바이트 안팎이면(`version https://git-lfs...`로
시작하는 텍스트) 실제 DB가 아니라 LFS 포인터입니다 — `git lfs pull`을 먼저 실행하세요.

**(A) 파일 전달받기** — 권장. `data/`에 넣으면 끝입니다.

**(B) 직접 만들기** — 약 6분

```bash
py -m pipeline.schema          # CSV → 표 생성 + 적재
py -m pipeline.embed_kb        # 지식베이스 22,500청크 임베딩 (5분)
py -m pipeline.embed_member    # 회원 900청크 임베딩 (30초)
```

`data/`에 원본 CSV들이 있어야 합니다.

---

## 실행 방법

**반드시 프로젝트 루트에서 `-m`으로 실행합니다.**

```bash
py -m app.engine.weights           # 검색어 → 가중치
py -m app.engine.recommend         # 가중치 → TOP 5
py -m app.engine.explain           # TOP 5 → 설명문
py -m app.features.search          # 전체 흐름 한 번에
py -m app.features.region_explain  # 동네 하나 설명 (시설명 근거)
py -m app.features.chat            # 추천 뒤 후속 질문
py -m pipeline.search_kb           # 저장된 벡터로 검색만 (디버깅용)
```

추천 알고리즘은 2026-08~09에 `pipeline/`에서 `app/engine/`으로 옮겼습니다 —
`py -m pipeline.weights` / `pipeline.recommend`는 더 이상 없습니다.

`py pipeline/schema.py`처럼 파일 경로로 실행하면 `ModuleNotFoundError`가 납니다.
`-m` 없이 실행하면 프로젝트 루트가 검색 경로에 안 잡히기 때문입니다.

---

## 확인하는 법

```bash
py -m pytest tests -q     # 테스트 4파일
bash check.sh             # 계층이 지켜지나 세 가지
```

`check.sh`는 세 가지를 셉니다.

| | 무엇 | 통과 기준 |
| --- | --- | --- |
| ① | 창구·엔진에 SQL이 있나 | 0곳 |
| ② | 함수 안 import 가 있나 | 0곳 |
| ③ | 계층 방향 (`tests/test_layers.py`) | `3 passed` |

②가 왜 규칙인가 — 함수 안 import 는 순환 참조를 **고치는 게 아니라 눈에 안 보이게
덮습니다.** 파일 맨 위만 봐서는 이 파일이 무엇에 기대는지 알 수 없고, 증상이
"서버는 뜨는데 특정 기능만 죽음"으로 나타납니다. 필요해지면 그건 공통 부분을
아래층으로 내리라는 신호입니다.

> Windows PowerShell 에는 `bash`·`grep` 이 없습니다. Git Bash 터미널에서 돌리거나
> (VSCode 터미널 `∨` → Git Bash), VSCode 전체 검색(`Ctrl+Shift+F`)을 쓰세요.

---

## 폴더 구조

```
Life-Embed-jh/
├── app/
│   ├── domain/            DB·네트워크·LLM 을 모르는 순수 함수 (테스트가 붙는 곳)
│   │   ├── dong.py          행정동 이름 표기 변형 (dong_variants)
│   │   └── masking.py       전화·이메일·이름·주소·연락처 문장 가리기 규칙
│   ├── core/              제일 밑바닥
│   │   ├── config.py        경로 · API키 · 모델명 · 7개 지표 · 청킹 대상 칸
│   │   └── db.py            SQLite 연결과 실행기 5개뿐
│   │                        (get_con · query · one · dicts · table_columns)
│   ├── tables/            표를 다루는 SQL. 여기에만 있다
│   │   ├── members.py       회원 프로필 · 가중치 · 페르소나 · 수정 · 집계
│   │   ├── regions.py       행정동 지표 · 시설 · 백분위 · 시세 · 수정
│   │   ├── chunks.py        임베딩 청크 조회와 재임베딩 쓰기(replace_*)
│   │   └── history.py       좋아요 · 검색기록 · 채팅기록 · 로그인 · 관리자로그 · 분석대화
│   ├── llm.py             임베딩 모델과 Claude 를 만드는 유일한 곳 (to_passage/to_query)
│   ├── engine/            추천 알고리즘
│   │   ├── weights.py       검색어 → 가중치
│   │   ├── recommend.py     가중치 → TOP 5
│   │   ├── explain.py       TOP 5 → 설명문
│   │   ├── housing.py       건물유형·거래유형·예산 → 시세 근접 필터·신뢰등급/거래건수/분포
│   │   └── resync.py        회원 한 명만 재임베딩 (관리자 수정 직후 반영)
│   └── features/          창구 — Life-Web 이 부르는 문. SQL 도 표 이름도 여기 없다
│       ├── search.py        search(query) 통합 창구
│       ├── region_explain.py  동네 하나를 시설명 근거로 설명
│       ├── chat.py          추천 뒤 후속 질문에 답변
│       ├── admin.py         관리자 조회·수정·대시보드 창구
│       ├── analysis.py      DB 집계를 Claude 에게 해석시키는 관리자 분석
│       ├── auth.py          임시 로그인 발급·검증
│       ├── survey.py        설문 답변을 Claude 에게 채점시키는 창구
│       └── privacy.py       DB 이름·지역명을 masking.py 규칙에 물려 주는 얇은 층
├── pipeline/              한 번만 돌리는 준비 작업 (배포에 안 따라감)
│   ├── schema.py            CSV → SQLite
│   ├── sample_kb.py         18.5만 명 → 2,500명 층화추출
│   ├── chunk_kb.py          페르소나 → 22,500청크
│   ├── embed_kb.py          청크 → 벡터
│   ├── embed_member.py      회원 100명 → 900청크 벡터
│   ├── search_kb.py         벡터 검색 (테스트용 CLI)
│   ├── fix_member_persona.py  회원 페르소나 불일치 교정 (1회성)
│   ├── io.py                CSV 읽기/쓰기 (utf-8 ↔ cp949 자동 판별)
│   └── prep/chunking.py     청킹 로직 (chunk_kb · embed_member · resync 공용)
├── tests/                 DB·서버·LLM 없이 도는 것만 둔다
│   ├── test_dong.py         행정동 이름 표기 변형
│   ├── test_masking.py      마스킹 (긴 이름부터 지우는 순서까지)
│   ├── test_percentile.py   백분위 동점 처리
│   └── test_layers.py       import 그래프가 한 방향인가
├── check.sh               계층이 지켜지나 세 가지를 센다
└── data/                  life.db·nemotron.csv 등은 Git LFS
    ├── life.db              약 73MB
    ├── master_dataset_v3.csv  427개 행정동 × 86칸 (밀도 62칸 + 시세 24칸)
    ├── 시세_지역별_전처리.csv  동×건물유형×거래유형별 신뢰등급·거래건수·분포
    └── 전처리 CSV들          문화시설 · 의료 · 학원 · 공원 · 점포 등
```

**층은 한 방향으로만 흐릅니다.**

```
0 domain  →  1 core  →  2 tables · llm  →  3 engine  →  4 features  →  Life-Web
```

아래층은 위층을 부르지 않습니다. `tests/test_layers.py`의 `LAYER` 표가 이 번호를
들고 있으므로, 폴더를 옮기면 그 표도 같이 고쳐야 합니다.

**SQL 은 `app/repositories/` 에만 있습니다.** 창구(`features`)와 엔진(`engine`)에는 SQL 도
표 이름도 없습니다 — 표가 바뀔 때 고칠 곳이 한 폴더로 모이게 하려는 것입니다.
`app/repositories/` 는 이름 붙은 함수만 냅니다(`WHERE` 조각이나 SQL 문자열을 인자로 받지 않음).

`app/`에는 `__init__.py`가 없는 네임스페이스 패키지가 섞여 있어, **저장소 루트가
검색 경로에 있어야** `app.*` / `pipeline.*`이 resolve됩니다. 위 `-m` 규칙이 그래서 필요합니다.

**계층 방향에서 한 곳만 예외입니다** — `app/engine/resync.py`가 `pipeline/prep/chunking.py`를
import합니다(`make_chunks`, `KB_KEYS`, `MEMBER_KEYS`). 청킹 규칙이 적재와 관리자 재임베딩
양쪽에서 똑같아야 해서 사본을 두지 않고 한 곳을 공유합니다. 청킹을 고칠 때 `pipeline/`만
보고 판단하면 관리자 수정 경로가 같이 바뀐 걸 놓칩니다.

---

## 관리자 창구 (`app/features/admin.py`)

`Life-Web`의 관리자 화면이 부르는 함수들입니다. 조회는 화이트리스트로 칸을 제한하고,
수정은 값 범위를 검사한 뒤(`_validate`) 저장합니다.

| 하는 일 | 함수 |
|---|---|
| 조회 | `list_members` · `get_member` · `list_regions` · `get_region` (지표 12개 + 427동 백분위) |
| 수정 | `update_member` · `update_region` |
| 참고 | `preview_member`(희망조건으로 TOP 5 미리보기) · `similar_members`(페르소나가 비슷한 회원) |
| 점검 | `health`(DB·캐시 상태) · `dashboard`(연령·성별·7지표 평균·청크 분포) · `recent_logs` |
| 개인정보 | `privacy_preview`(원본 ↔ 가린 것 나란히, `changed`가 0이면 아무것도 안 가려진 것) |
| 캐시 | `clear_caches` |

**회원을 고칠 때는 세 곳이 항상 같이 움직여야 합니다.**
① DB 값 → ② 페르소나를 고쳤다면 벡터 재생성(`resync_member`) → ③ 캐시 비우기(`_clear_caches`).
하나라도 빠지면 "화면엔 새 값인데 추천은 옛날 것"이 됩니다. 수정 이력은 `admin_log` 표에
남습니다(`write_admin_log`, 표가 없으면 `ensure_admin_log`가 만듭니다).

### 개인정보 마스킹

내보내기 전에 페르소나 문장에서 전화번호·이메일·회원 이름·자치구/행정동 주소를 가리고,
연락 수단이 적힌 문장("카톡 아이디 abc123으로 주세요")은 문장째 걷어냅니다.

- `app/domain/masking.py` — 규칙만 있는 순수 함수. DB를 모르고, 이름 목록을 밖에서 받습니다.
- `app/features/privacy.py` — DB에서 이름·지역명을 읽어 그 규칙에 물려 주는 얇은 층.
  앱은 `mask_text()` 하나만 부릅니다. 회원 이름이 바뀌면 `privacy.reset()`으로 캐시를 버립니다
  (`admin._clear_caches()`가 이미 부릅니다).

**완벽하지 않습니다.** 목표는 "실수로 통째로 흘러나가는 것"을 막는 것이고,
무엇이 안 가려지는지는 `privacy_preview()`로 눈으로 확인해야 합니다.
자치구 이름은 두 글자 이상만 줄임말로 잡습니다 — `중구` → `중`은 집중·중요·도중을
921회 오탐해서 뺐습니다.

---

## 설계 원칙

### 자치구(25개) 단위 변수를 순위 계산에 쓰지 않는다

같은 구의 행정동이 전부 같은 값을 받아 구별할 정보가 없어집니다.
모든 인프라 지표는 **행정동 단위 밀도(개수 ÷ km²)** 로 변환해 씁니다.

소음·미세먼지처럼 구 단위밖에 없는 값은 참고 정보로만 쓰고,
표시할 때 "○○구 평균"임을 반드시 밝힙니다.

### 백분위로 바꾼 뒤 계산한다

밀도 원값을 그대로 곱하면 단위가 제각각입니다
(학원 1,263개/km² vs 공원 19개/km²). 그래서 모든 지표를
427개 동 중 백분위(0~100)로 바꾼 뒤 가중합합니다.

**같은 값은 반드시 같은 점수를 받습니다.** 밀도 칸에는 0이 대량으로 몰려 있어서
(도서관 275/427, 지하철역 169, 경찰관서 164) 동점 처리가 필수입니다.
예전에는 `argsort()`를 두 번 쓰는 방식이라 동점이 **DB 저장 순서(행정동 코드 순)**로
줄 세워졌고, 도서관이 똑같이 0곳인데 영등포구는 평균 56점 · 성동구는 14점을 받는
자치구 단위 편향이 생겼습니다. 지금은 동점 그룹이 순위를 평균내어 나눠 갖습니다.

백분위 구현은 두 곳에 있고 **규칙이 같아야 합니다** — `app/engine/recommend.py`의
`to_percentile()`(427개 배열, 순위 계산용)과 `app/repositories/regions.py`의
`column_percentile()`(칸+값 하나, 화면 표시용). 둘 다 화면에서 똑같이 "상위 N%"로
보이기 때문입니다. 입력이 달라서 **합칠 수는 없고**, 한쪽만 고치면 같은 동네가
화면마다 다른 점수로 보입니다.

### 절대점수만 쓰면 "만능 동네"가 항상 이긴다

골고루 높은 동네가 어떤 검색어를 넣어도 1위가 됩니다.
`build_relative`로 "그 동네 안에서 이 지표가 상대적으로 강점인 정도"를
같이 반영합니다(`mix` 파라미터로 비율 조절).

### 가중치 편차를 증폭한다

교육 4.6 vs 나머지 3.0은 비율로 1.5배뿐이라, 7개를 다 더하면
교육이 전체의 20%밖에 차지하지 못해 순위를 못 바꿉니다.
`sharpen=6`으로 평균 대비 편차를 지수로 키워, 사용자가 중시한 지표가
실제로 순위를 좌우하게 만듭니다.

### 예산은 "낮을수록 좋다"가 아니라 "목표가에 가까울수록 좋다"

처음엔 시세를 "무조건 낮을수록 좋다"로 볼 뻔했지만, 목표가를 구체적으로 준 경우
(예: "전세 4억 정도")엔 다릅니다. 강남처럼 비싼 동네에서도 그중 저렴한 집을 찾는
사람만 있는 게 아니라, 일부러 그 가격대 매물을 찾는 사람도 있기 때문입니다.

그래서 목표가가 있으면 `housing.py`가 목표가 대비 ±30%(`tolerance`) 안의 동만
후보로 남기고, 그 안에서 기존 7개 지표로 순위를 매깁니다. 목표가가 없을 때만
"시세는 낮을수록 좋다"를 8번째 참고 신호로 살짝 얹습니다(`DEFAULT_PRICE_WEIGHT`).

### 검색어를 사람 묘사로 바꿔서 검색한다

사용자 검색어는 "좋은 곳"처럼 **장소**를 찾는 문장인데,
회원 벡터에 담긴 건 **사람**을 묘사한 문장입니다.
성격이 다른 두 문장을 그대로 비교하면 엉뚱한 결과가 나옵니다.

그래서 Claude가 검색어를 `persona_query`("초등학생 자녀를 키우며
교육 환경을 중시하는 부모")로 바꾼 뒤 그 문장으로 검색합니다.

---

## 주의할 점

**임베딩 모델을 바꾸면 벡터를 전부 다시 만들어야 합니다.**
현재 `intfloat/multilingual-e5-small`(384차원). 다른 모델은 차원부터 다릅니다.

**e5 접두사 규칙** — 저장할 문서는 `passage:`, 검색 질의는 `query:`를 붙입니다
(`to_passage` / `to_query`). LangChain이 자동으로 붙여 주지 않습니다.

**행정동 이름 표기가 파일마다 다릅니다.** `고덕제1동` vs `고덕1동`.
`app/domain/dong.py`의 `dong_variants()`가 양쪽을 다 시도합니다
(`app/repositories/regions.py`가 이걸 import해서 씁니다 — 사본을 만들지 마세요).

**LLM 프롬프트에 가중치를 실었으면 그 지표의 점수도 함께 실으세요.**
근거 수치 없이 항목 이름만 보이면 Claude가 그 항목을 지어내서 설명합니다.
특히 `시세` 점수는 `invert=True`라 **값이 클수록 저렴하다**는 뜻이므로,
방향 설명을 같이 주지 않으면 "시세 85점"을 "비싸다"로 정반대 해석합니다.

**`INDICATORS` 순서를 바꾸지 마세요.** 순서로 값을 꺼내는 코드가 있습니다.

---

## 데이터 출처

| 데이터 | 출처 |
|---|---|
| 행정동 인프라 | 서울열린데이터광장 |
| 주거 만족도 | 서울시 주거실태조사 마이크로데이터 (15,730명) |
| 페르소나 | NVIDIA Nemotron-Personas-Korea |
| 행정동 경계 | 통계청 SGIS |

---

## 아직 안 된 것

- 학교·버스·CCTV는 `master_dataset_v3`의 밀도(개수/km²)로만 순위 계산에 쓰이고,
  `facilities`(시설 "이름" 목록)엔 아직 없음 — 문화시설·의료·학원·공원·점포 5종만 있음
- 필터 지원 (`exclude_gu` — "강남 외" 같은 제외 조건)
- `schema.py`의 4·5단계(CSV 스캔·타입 추론·FK 추론)가 `if __name__` 없이 모듈 최상위에서
  실행됨 — `import pipeline.schema`만 해도 즉시 돈다
- 월세는 시세 25~75% 분포를 못 보여줌 — 원본 `시세_지역별_전처리.csv`에 `월임대료`용
  25/75 분위 칼럼 자체가 없음(매매가·보증금엔 있음). 신뢰등급·거래건수는 월세도 정상 표시됨
- 추천 정확도(hit@k)를 재는 평가 도구가 없음 — 지금 실측 기록은 전부 **속도**뿐
---

## 논의 필요

### 목표가 일치도를 순위에도 반영할 것인가 (2026-09-01 제기)

현재 `housing.py`의 `housing_fit_score()`(목표가 대비 0~100점)는 **후보를 추리는 필터로만**
쓰입니다. `app/features/search.py`의 `recommend_by_weights()`가 `matching_regions()`로 tolerance
(±30%) 안의 동만 남긴 뒤, 그 안에서의 순위는 기존 7개 지표로만 매깁니다.

그래서 "전세 6억 5천" 검색에서 62,000만원인 동(일치도 85점)과 73,000만원인 동(59점)이
**순위 계산에서는 완전히 동등하게** 취급됩니다.

- **지금대로 두는 쪽** — 가격은 "들어갈 수 있냐 없냐"의 문제고, 그 안에서는 생활
  인프라로 고르는 게 맞다. tolerance가 이미 ±30%로 좁으므로 후보는 전부 "예산에 맞는 곳"이다.
- **순위에 넣는 쪽** — 위 "설계 원칙"의 *예산은 목표가에 가까울수록 좋다*를 필터에서만
  지키고 순위에서는 버리는 셈이다. 일치도를 8번째 신호로 넣으면 원칙이 끝까지 일관된다.

넣기로 결정하면, `recommend_by_weights()`의 housing 분기에서 목표가가 없을 때 `시세`를
얹는 것과 **똑같은 방식**으로 `일치도`를 넣으면 됩니다(`scores`/`relative`/`weights` 세 곳).

### 설명문의 시세 어법 (위 결정과 함께 볼 것)

순위 반영 여부와 별개로, 지금은 Claude에게 **사용자가 말한 목표 금액 자체가 전달되지 않고**,
`price_fit_score()`가 `abs()`를 쓰기 때문에 방향(목표보다 비싼지 싼지)도 사라집니다.
그래서 "원하시는 가격대보다 조금 높은 편입니다" 같은 답변이 원리적으로 불가능합니다.
같은 일치도 85점이 62,000만원(싼 쪽)일 수도 68,000만원(비싼 쪽)일 수도 있습니다.

목표가와 방향을 프롬프트에 같이 넣어야 합니다 — 구체적인 수정안은 `STUDY.md` 16절 참고.
