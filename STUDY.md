# 기록 방법
    - 사용자는 코딩을 막 시작한 초보개발자.
    - 함수나 기능에 대한 설명 필요
    - 원본 코드 -> 수정할 코드를 알기 쉽게 표기
    - 예시:
        클릭은 되는데 드래그만 안 되는 이유

        슬라이더를 끄는 건 mousedown → mousemove → mouseup 세 단계예요. 그런데 search.js가 문서 전체에 mousemove 리스너를 걸어놨죠:

       ```
        document.addEventListener("mousemove", (e) => {
        ...
        updateMagnetic(mx, my);
        });
        ```

        떠다니는 단어의 자석 효과예요. 이게 계속 돌면서 getBoundingClientRect()를 14번씩 호출해요. 검색 화면이 사라진 뒤에도요.

        클릭(한 번의 이벤트)은 되는데 드래그(연속 이벤트)가 버벅이는 게 이 증상과 맞아요.

        고치기 — 화면이 걷히면 자석을 멈춘다

        search.js의 updateMagnetic 맨 앞에 한 줄 넣으세요.

        ```
        function updateMagnetic(mx, my) {
        // 검색 화면이 걷힌 뒤에는 계산할 이유가 없다.
        // 그대로 두면 mousemove 마다 getBoundingClientRect 를 14번씩 부르느라
        // 슬라이더 드래그 같은 다른 조작이 버벅인다
        const screen = document.getElementById("searchScreen");
        if (!screen || screen.classList.contains("out")) return;

        document.querySelectorAll(".ss-word").forEach((word) => {
            ...    
        ```

---

# 진행 상황

시세(매매가·보증금·월세) 반영은 아래 "완료된 작업 요약" 기준으로 전부 끝난 상태다. 예전에 이
문서에 쌓여 있던 단계별 계획(빈 표 설계 → `housing.py` 신설 → `attach_price()` → 신뢰등급·
거래건수·분포까지, 총 13개 섹션)은 전부 구현·검증됐으므로 지웠다 — 실제 동작은 코드
(`app/core/db.py`, `pipeline/housing.py`, `pipeline/recommend.py`,
`app/features/pipeline_api.py`)를 기준으로 볼 것. 파일·행 단위 변경 내역은
`changelog_시세반영.md`에 남아 있다.

## 완료된 작업 요약

- **목표가 근접 필터** — `pipeline/housing.py`의 `DEAL_COLUMNS`·`matching_regions()`·
  `housing_fit_score()`. 사용자가 건물유형·거래유형·예산을 주면 그 조건 ±30%(`tolerance`)
  안의 동만 후보로 남기고, 후보가 5개 미만이면 종합 점수 상위 20곳으로 대체(fallback)한다.
- **목표가 없을 때** — `pipeline/recommend.py`의 `PRICE_COLUMNS`·`load_price_values()`·
  `build_price_score()`. 12개 시세 칼럼(4건물유형×3거래유형)의 평균 백분위를 "시세" 8번째
  신호로 얹는다. `INDICATORS`(7개)엔 안 섞는다 — `build_relative()` 기준선이 바뀌는 부작용을
  피하려고 별도 보관.
- **구조화된 값** — `pipeline/housing.py`의 `attach_price()`가 `detailed`의 각 동네에
  `d["price"]`로 중앙값·일치도·거래건수·신뢰등급·출처·금액_25/75를 붙인다. 프론트엔드가 표로
  바로 쓸 수 있다. `app/core/db.py`의 `region_price_detail()`이 `시세_지역별_전처리` 표에서
  신뢰등급·거래건수·분포를 조회하는 실제 쿼리다 — `master_dataset_v3`엔 중앙값만 있고 이
  상세 정보는 없다.
- **LLM 프롬프트 연동** — `pipeline/explain.py`(TOP5 설명), `app/features/region_explain.py`
  (동네 하나 설명), `app/features/chat.py`(후속 질문)가 각각 시세 중앙값·조건 일치도·
  신뢰등급·거래건수·분포를 문장으로 만들어 Claude에게 넘긴다. 신뢰등급·거래건수·분포는
  2026-08-31에 `pipeline/housing.py`의 `_format_price_note()`/`region_price_note()`로
  추가했고, SYSTEM_PROMPT에도 "표본이 적거나 신뢰등급이 낮으면 참고용이라고 밝히라"는
  지침을 같이 넣었다.
- **검색어 → 가격 조건 추출** — `pipeline/weights.py`의 `ask_claude()`가 "전세 4억 정도"류
  검색어에서 건물유형·거래유형·예산·보증금을 뽑는다. `search(query, housing_override=...)`로
  화면 슬라이더 값이 검색어보다 우선하도록 override할 수 있다.

## 이 저장소(엔진) 밖에 남아 있던 일

`Life-Web/services/engine.py`가 `search()`/`recommend_by_weights()`를 부를 때 `housing` 인자를
안 넘기고, 자기 저장소의 옛 `services/price.py`(`시세_지역별.csv`를 따로 읽어 사후 감점하는
방식)를 덧씌우고 있었다 — 두 파이프라인이 같은 문제를 각자 다른 방식으로 풀어서 "설명문 순위
≠ 화면 순위" 괴리가 생기는 원인이었다. 이 저장소(엔진) 쪽은 `attach_price()`가 신뢰등급·
거래건수·분포까지 구조화된 값으로 이미 제공하므로, `Life-Web/services/price.py`와
`Life-Web/data/시세_지역별.csv`는 더 이상 필요 없다 — 정리는 `Life-Web/study.md`에서 다룬다.

## 여전히 유효한 주의사항

- **시세는 동네 전체의 중앙값이지, 특정 매물 가격이 아니다.** 화면·설명문 어디서든 "이 동네
  아파트 전세는 3억 8천이에요"가 아니라 "중앙값이 3억 8천이에요"로 표현해야 한다.
- **월세는 "보증금"과 "월세" 두 금액을 같이 본다.** `FIELD_WEIGHT = {"예산": 0.7, "보증금":
  0.3}`로 월세가 더 크게 반영되게 했다 — 감으로 잡은 비율이라 실제로 써보면서 조정이 필요할
  수 있다.
- **`tolerance=0.3`(±30%)도 감으로 잡은 값이다.** 너무 좁으면 fallback만 계속 타고, 너무
  넓으면 필터를 건 의미가 없어진다.
- **`건물유형` 별칭은 프론트엔드 코드로 재확인할 것.** "빌라"·"원룸" 같은 표시용 이름이
  실제로 쓰이면, `ask_claude()` 프롬프트와 `DEAL_COLUMNS`의 키를 원본 데이터 값
  (단독다가구/아파트/연립다세대/오피스텔) 네 가지로 정규화해야 한다.
- **월세는 분포(`매매가_25/75`, `보증금_25/75`)가 항상 빠진다.** `시세_지역별_전처리`에
  월세용 25/75 칼럼이 없기 때문이다 — 원본 데이터 자체의 한계.
- **가격 신뢰등급·거래건수·분포 note(`region_price_note()`)는 조합마다 새로 쿼리한다.**
  `chat.py`는 동네 하나당 최대 12번(건물유형4×거래유형3 중 값 있는 조합만) 호출하는데,
  TOP5 규모(최대 60쿼리/요청)에선 문제없지만 호출이 훨씬 잦아지면 `region_densities()`
  캐싱과 같은 방식으로 최적화할 수 있다.
- **note에서 `출처`가 "해당지역"이면 아예 생략한다.** 그 동네 자체 표본이 있다는 뜻이라
  따로 알릴 필요가 없어서다. "자치구"/"법정동" 값으로 대체된 경우만 문장에 남긴다.

---

# 15. (2026-08-31) persona 청크 2차 분할 폴백 추가

## 왜 필요한가

임베딩 모델(`intfloat/multilingual-e5-small`, `app/core/config.py`)의 입력 한도는 512
토큰이다. `HuggingFaceEmbeddings`는 이걸 넘으면 에러 없이 **조용히 뒷부분을 잘라버린다**
(silent truncation). `pipeline/chunk_kb.py`의 `make_chunks()`는 `MIN_LENGTH`(20자, 하한)만
검사하고 상한 검사가 없었다 — 칼럼 텍스트 하나가 통째로 청크 하나가 됐다.

실측해보니(`data/kb_persona.csv`의 `CHUNK_COLUMNS` 9개 칼럼 기준) 현재 데이터는 칼럼 전체
길이가 최대 268자로 512토큰까지 여유가 많아 지금 당장 잘리는 사례는 없다. 문제는 **앞으로
회원가입 시 서술형 답변을 자유 입력으로 받을 계획**이라는 점이다. 이 경우 글자 수를 강제할
수 없고, 특히 실사용자는 마침표 없이 길게 이어 쓰는 경우가 흔해서 문장 경계로만 나누는
방식은 뚫릴 수 있다.

## 고친 것 — `pipeline/chunking.py` 새로 만들고, 두 파일이 같이 쓰게 함

`chunk_kb.py`(지식베이스)와 `embed_member.py`(회원)의 `make_chunks()`는 코드가 완전히
똑같았다(주석에도 "03번과 같은 방식"이라고 적혀 있었음). 그래서 텍스트 쪼개는 로직은 새 파일
`pipeline/chunking.py` 하나에만 만들고, 두 파일이 그 함수를 가져다 쓰게 했다 — 한쪽만
고치고 한쪽을 빠뜨리는 실수를 막기 위해서다(`app/core/llm.py`의 `to_passage`/`to_query`를
한 곳에 모은 것과 같은 이유).

```python
# pipeline/chunking.py (새 파일)
import re

# 토큰 수를 정확히 재려면 임베딩 모델 tokenizer 가 필요한데, 그러려면 무거운
# 모델을 청킹 단계에서부터 올려야 한다. 대신 글자 수로 넉넉하게 안전 마진을
# 두고 근사한다 (한국어는 토큰:글자 비율이 문장마다 달라 딱 맞추기 어렵다)
MAX_LENGTH = 350

# 문장이 끝나는 지점(. ! ?) 뒤에 공백이 오면 그 자리에서 나눈다
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def split_long_text(text, max_length=MAX_LENGTH):
    """긴 텍스트를 max_length 글자 이하 조각 여러 개로 쪼갠다.

    1단계 — 문장 단위로 나눈다. 문장 하나가 max_length 안이면 그대로 둔다.
    2단계 — 마침표가 없어서 문장이 안 나뉘는 경우(사용자가 마침표 없이
            길게 이어 쓴 경우), 그 조각만 글자 수로 강제로 잘라낸다.
    """
    text = text.strip()
    if len(text) <= max_length:
        return [text]

    pieces = []
    for sentence in _SENTENCE_END.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(sentence) <= max_length:
            pieces.append(sentence)
        else:
            # 문장 분리로도 못 줄인 조각 -> 글자 수로 강제 분할
            for i in range(0, len(sentence), max_length):
                pieces.append(sentence[i:i + max_length])

    return pieces
```

## 두 호출부에 붙이기

`chunk_kb.py`의 `make_chunks()` — 원본은 칼럼 텍스트 하나를 그대로 청크 하나로 만들었다.

```python
# pipeline/chunk_kb.py (원본)
for column in CHUNK_COLUMNS:
    text = (row.get(column) or "").strip()
    if len(text) < MIN_LENGTH:
        continue
    chunks.append({
        "uuid": row["uuid"],
        "district": row["district"],
        "category": column,
        "text": text,
    })
```

이걸 `split_long_text()`로 한 번 더 통과시키도록 고쳤다. 텍스트가 짧으면 `split_long_text`가
`[text]`(원소 1개짜리 리스트)를 그대로 돌려주므로, 짧은 텍스트는 예전과 똑같이 청크 1개가
나온다 — 동작이 바뀌는 건 350자를 넘는 긴 텍스트뿐이다.

```python
# pipeline/chunk_kb.py (수정)
from pipeline.chunking import split_long_text
...
for column in CHUNK_COLUMNS:
    text = (row.get(column) or "").strip()
    if len(text) < MIN_LENGTH:
        continue
    for piece in split_long_text(text):
        if len(piece) < MIN_LENGTH:
            continue
        chunks.append({
            "uuid": row["uuid"],
            "district": row["district"],
            "category": column,
            "text": piece,
        })
```

`pipeline/embed_member.py`의 `make_chunks()`도 `customer_id` 버전으로 똑같이 고쳤다.

`chunk_index`(몇 번째 조각인지) 필드는 추가하지 않았다 — 지금은 디버깅 편의 정도의
가치라 범위를 최소로 유지했다. 나중에 "어떤 조각이 검색에 걸렸는지" 추적할 일이 생기면
그때 추가해도 된다.

## 왜 집계 로직(`weights.py`)은 안 건드렸나

`pipeline/weights.py`의 `find_similar_members()`는 이미 "한 사람이 청크 여러 개로 걸릴 수
있다"를 전제로 `customer_id` 기준 최고 점수만 남기는 방식으로 짜여 있었다(주석에도 그렇게
적혀 있음). 칼럼 하나가 청크 여러 개로 늘어나도 이 구조는 그대로 맞아떨어져서, 실제로 고칠
곳은 `chunk_kb.py`/`embed_member.py` 두 곳(정확히는 `pipeline/chunking.py` 한 곳 + 호출부
두 곳)으로 끝났다.

## 검증

- `python -m pipeline.chunking` — 문장 있는 긴 텍스트는 문장 단위로, 마침표 없는 긴 텍스트는
  350자씩 강제로 잘리는 걸 확인.
- `python -m pipeline.chunk_kb` 재실행 — 결과가 여전히 "2,500명 → 청크 22,500개"로 변경 전과
  동일. 현재 데이터엔 350자 넘는 칼럼이 없어서(최대 268자) 분할이 실제로 일어나지 않았고,
  기존 출력과 완전히 같다는 뜻 — 회귀 없이 안전장치만 추가된 것을 확인.
- `embed_member.load_members`/`make_chunks`를 5명 샘플로 직접 불러 청크가 정상 생성되는 것도
  확인(전체 임베딩은 시간이 걸려 생략).

## 실측 근거 (2026-08-31 확인)

`data/kb_persona.csv`의 `persona`/`professional_persona`/`sports_persona`/
`arts_persona`/`travel_persona` 5개 칼럼을 마침표 기준으로 쪼개 문장 길이를 재봤다.

```
총 문장(청크 후보) 수: 20,245
최대 문장 길이(글자): 166
평균: 79.9
중앙값: 78
150자 넘는 문장 수: 8
300자 넘는 문장 수: 0
```

즉 지금 LLM이 생성한 정형화된 페르소나 텍스트만 놓고 보면 문장 하나가 500토큰을 넘는 경우는
사실상 없다. 이 폴백이 필요한 이유는 지금 데이터 때문이 아니라, **아직 들어오지 않은 회원
서술형 입력**을 대비하기 위함이라는 걸 기억할 것 — 지금 데이터로 테스트해서는 2차 폴백이
동작할 일이 없으니, 검증할 때는 일부러 마침표 없이 긴 텍스트를 만들어 넣어봐야 한다.

## 주의할 점

- **문장 분리 정규식만으로는 안전하지 않다.** 마침표를 안 찍는 입력(모바일 사용자가 흔히
  그렇다)은 문장 분리기에 "문장 하나"로 잡혀서 그대로 한도를 넘길 수 있다 — 그래서 2차
  강제 분할 폴백이 "혹시 몰라 넣는 것"이 아니라 핵심 안전장치다.
- **`intfloat/multilingual-e5-small`을 다른 모델로 바꾸면 토큰 한도(512)와 글자/토큰 비율이
  같이 바뀐다.** 상수를 하드코딩한다면 어디 한 곳(`config.py`)에만 두고, 모델 변경 시 같이
  검토할 것.

## 다음에 할 일 — 회원가입으로 들어올 새 회원은 아직 청킹 대상이 아니다

지금 `pipeline/embed_member.py`는 `nemotron.csv`(테스트용 대용량 데이터) 앞 100명을
"회원"으로 미리 정해두고, 실행할 때마다 `member_chunk` 표를 통째로 지우고 처음부터 다시
만드는 **일괄 배치** 방식이다(`__main__`의 `DELETE FROM member_chunk` 부분).

실제로 회원가입 기능이 생기면, 신규 회원 한 명이 서술형 답변을 낼 때마다 그 텍스트만
쪼개서(`split_long_text()` 그대로 재사용 가능) 임베딩하고 `member_chunk`에 **한 줄만
추가(INSERT)**해야 한다 — 지금처럼 전체를 지우고 다시 만들면 이미 가입한 다른 회원들의
데이터까지 매번 날아간다. 즉 오늘 만든 `split_long_text()`는 그대로 재사용할 수 있지만,
`embed_member.py`의 "지우고 전부 다시 만들기" 흐름 자체는 회원가입 기능을 만들 때 별도로
"한 명만 추가하는" 함수로 새로 짜야 한다. 이건 이번 작업 범위 밖이라 코드는 아직 안
건드렸다 — 회원가입 기능을 실제로 만들 때 이 섹션을 참고할 것.


## 신규 및 수정한 파일 목록<다솜>
Life-Embed-jh: app/core/db.py(수정), app/features/pipeline_api.py(수정, 지난번 추가한 recommend_by_weights_explained), app/features/admin.py(신규, 방금 고침)
Life-Web: main.py, services/engine.py, services/lifetype.py(지난번 버그 수정), routers/survey.py(신규), services/persona_type.py(신규)

## 수정사항
문법 오류 수정 — app/engine/explain.py:117에 f-string 안에 같은 종류의 따옴표("..." 안에 ", ")를 중첩해서 쓴 코드가 있어 Python이 아예 파싱을 못 하고 죽었습니다. 홑따옴표로 바꿔서 고쳤고, import가 그 지점은 통과하는 걸 확인했습니다.

새 파일 app/repositories/members.py 추가 (다만 지금은 `member_chunks()`, `member_weigths()` — 오타 있음 — 두 함수뿐)

Life-Web/services/persona_type.py (신규) — 서술형 15문항 → 축 점수 → 유형 판정 → 7지표 가중치. `lifetype.py`의 `AXES/TYPES/AXIS_TO_WEIGHT/type_of()`를 그대로 재사용해서 1차·2차가 같은 표를 씁니다(따로 사본을 두지 않음). LLM 없이 규칙 기반으로 즉시 계산됩니다. 독립 실행해서 확인했습니다

**Life-Embed-jh/app/features/pipeline_api.py**에 recommend_by_weights_explained(weights, persona_query, ...) 추가 `recommend.py`(recommend_by_weights)와 `explain.py`(explain, find_cases)만 그대로 재사용합니다. 설문은 이미 문항마다 축이 정해져 있어 가중치를 LLM이 추정할 필요가 없거든요.

**Life-Web/services/engine.py**에 `get_survey_recommendation()` 래퍼 추가, `Life-Web/routers/survey.py`(신규) — POST /api/survey가 answers(15문항)를 받아 위 파이프라인을 태우고 /api/predict와 같은 모양(topRegions, explanation 등)으로 응답합니다. `main.py`에도 등록했습니다.

끝까지 실서버로는 확인 못 한 이유
routers/survey.py → services/engine.py를 import하는 순간 아까 발견했던 그 문제에 다시 걸립니다:
ModuleNotFoundError: No module named 'app.features.admin'

## 발견하고 고친 것
admin.py가 기대하는 DB 조회 함수 10개가 db.py에 없었습니다 — customer_list, customer_one, customer_preferences, customer_persona, region_list, region_one, update_customer, update_preferences, update_region 등. 브랜치들을 뒤져보니 origin/jihye 브랜치의 `db.py`에는 이 함수들이 이미 있더라고요(순수 추가분, 지금 db.py랑 충돌 없음 — diff 확인함). 그걸 그대로 옮겨왔습니다.
이름이 안 맞는 게 하나 있었습니다 — admin.py는  `column_percentile`이라는 함수를 import하는데, db.py엔 `to_percentile`이라는 이름으로만 있었습니다(jihye 브랜치에도 column_percentile은 어디에도 없었어요). `admin.py` 쪽을 `to_percentile`로 맞췄습니다.

