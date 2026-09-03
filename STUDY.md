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


<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> 2acb0cb96cb318ef1d0c68e46d1e961ab2d526cd
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

# 16. (2026-09-01) 추천 결과와 LLM 답변이 이상한 원인 5가지

`a529501` 머지에서 `db.py`의 `import re`가 사라져 `NameError`가 났고 그건 해결했다. 그런데
파이프라인이 돌기 시작하니 **추천 순위와 Claude 설명문이 이상하다**는 증상이 남았다.
원인은 `NameError`와 무관한, **원래부터 있던 버그 5개**였다 — 지금까지는 파이프라인이 죽어
있어서 결과를 눈으로 볼 일이 없었을 뿐이다.

수정 코드는 전부 반영 완료. 구체적인 코드는 `git log`/현재 파일을 볼 것. 여기엔 **왜 그게
버그였는지와 어떻게 찾았는지**만 남긴다.

## 어떻게 찾았나 — 파이프라인을 돌리지 않고

파이프라인을 실행하면 Claude 호출 비용이 들고, 무엇보다 **결과가 이상하다는 걸 확인할 뿐 왜
이상한지는 안 나온다.** 그래서 두 가지만 썼다.

1. `data/life.db`에 **읽기 전용 SELECT** — 벡터 차원·노름, 밀도 칸의 결측/0 비율, `user_preferences` 분포
2. 프로젝트 코드를 실행하는 대신 **문제의 계산식만 검증용 스크립트로 옮겨 적어**, 현재 코드와
   고친 코드의 결과를 나란히 비교

먼저 **정상인 것**부터 확인해 원인 후보에서 지웠다:

```
member_chunk 900행 / kb_chunk 22,500행, NULL 0건, 차원 384, 노름 전부 정확히 1.0000
member_chunk 회원 100명 = user_preferences 100명 (교집합 100)
INDICATOR_COLUMNS 가 요구하는 밀도 칸 12개 전부 존재, NULL 0건
```

즉 임베딩·BLOB·정합성은 멀쩡했다. `AGENTS.md`가 경고한 "dtype이 어긋나 384가 192로 읽히는"
사고도 없었다(노름이 정확히 1.0인 것이 그 증거 — 차원을 잘못 읽으면 1이 안 나온다).
**원인은 벡터가 아니라 점수 계산과 프롬프트 조립에 있었다.**

---

## [1] 치명 — 백분위가 동점을 처리하지 않았다 (`recommend.py`)

`values.argsort().argsort()`는 순위를 구하는 흔한 관용구지만 **동점을 처리하지 않는다.**
`argsort`는 안정 정렬이라 값이 같으면 배열 순서를 유지하는데, 그 순서는 `region_densities()`의
`SELECT`에 `ORDER BY`가 없어 **DB 저장 순서 = 행정동 코드 순**이다.

결과: 도서관이 똑같이 0곳인 275개 동이 0점~64점으로 강제로 줄 세워졌고, **행정동 코드가 큰
자치구가 시설이 없어도 점수를 더 받았다.**

```
'도서관 0곳'으로 완전히 동일한 275개 동의 점수, 구별 평균
  영등포구 56.1점 · 구로구 55.1 · 금천구 54.8  ...  광진구 14.6 · 성동구 14.1
```

같은 문제가 `지하철역_밀도`(0인 동 169개), `경찰관서_밀도`(164개)에도 있었다.

**순위가 실제로 뒤집혔다** — "애들 학원 보내기 좋은 곳":

```
[고치기 전]                          [고친 뒤]
송파구 방이1동  78.8 (교육 95)  ->  노원구 중계1동  78.9 (교육 98)
노원구 중계1동  78.7 (교육 98)  ->  송파구 방이1동  77.8 (교육 95)
성동구 행당제2동 75.8 (교육 95)  ->  마포구 염리동   75.6 (교육 96)
```

교육 98점짜리가 95점짜리에게 1위를 내주고 있었다.

**고친 것**: `argsort` 한 번으로 순위를 구한 뒤 **동점 그룹은 순위 평균을 나눠 갖게** 했다.
검증: 0곳인 동들의 점수 폭이 `0.0~64.3` → `32.2~32.2`(단일값)로 수렴.

## [2] 치명 — `blend()`가 사용자가 말한 관심사를 깎았다 (`weights.py`)

`user_preferences` 100명의 실제 분포:

```
교육 평균 1.65  분포 {1:70, 2:9, 3:9, 4:10, 5:2}   <- 100명 중 70명이 1점
상권 평균 3.61 · 녹지 평균 3.53                     <- 아무도 요청 안 해도 3보다 높다
```

`blend()`는 이 **편향된 평균을 7개 지표 전부에 무조건 30% 섞었다.** Claude가 프롬프트 규칙대로
"교육 5, 나머지 3"을 내놔도 교육은 4.0으로 깎이고 상권·녹지는 3.2로 올라갔다. `recommend()`가
`(w / mean_w) ** 6`으로 증폭하므로 이 작은 차이가 순위에서 크게 벌어진다.

```
교육이 순위에 미치는 영향력:  초안 78.1%  ->  blend 통과 후 47.4%
상권(사용자가 말한 적 없음):  0.58배      ->  1.11배 (약 2배 상승)
```

**설계 판단** — 보정 자체를 없애는 건 과하다. 잘못된 건 섞는 비율(`CLAUDE_RATIO`)이 아니라
**섞는 대상**이었다. `SYSTEM_PROMPT` 규칙 1이 "말하지 않은 지표는 전부 3점"이라고 이미 정해
뒀으므로, **초안이 3점이 아닌 지표 = 사용자가 말한 지표**로 판별해 보정에서 제외했다
(`NEUTRAL = 3`). 회원 평균은 "말하지 않은 칸을 채우는" 용도로만 쓴다.

검증: 교육 영향력 47.4% → 77.5%. 부정 표현("번화가는 싫어요" → 상권 2점)도 그대로 보존된다.

## [3] 중 — 프롬프트에 가중치만 있고 점수가 없는 "시세" (`explain.py`)

가격 조건이 없는 검색에서 `pipeline_api`가 가중치에 `"시세"`를 8번째로 얹는데(`DEFAULT_PRICE_WEIGHT
= 3`), 점수를 붙이는 `with_scores()`는 `INDICATORS` 7개만 돌았다. 그래서 Claude가 받는 글이
**"시세 가중치 3은 있는데 시세 점수는 없고, 시스템 프롬프트는 있는 게 7개뿐이라고 한다"**는
모순 상태가 됐다. 이럴 때 모델은 빠진 칸을 스스로 메운다 — 그게 근거 없는 "가격 부담이 적다"였다.

> **처음엔 "시세를 프롬프트에서 숨기자"고 처방했다가 철회했다.** 순위 기여가 2~4%뿐이라
> 숨기는 게 맞다고 봤는데, 제품 의도는 "시세에 대해 한마디 덧붙이는 것"이었다. 문제는
> 시세가 **있다는 것**이 아니라 **가중치와 점수가 짝이 안 맞는 것**이었다.

**고친 것**: `with_scores()`가 `INDICATORS`로 자르지 않고 `scores`에 실제로 있는 지표를 전부
싣게 했다. 그리고 `SYSTEM_PROMPT`에 **방향 설명**을 넣었다 — `build_price_score()`가
`invert=True`라 **값이 클수록 저렴**하기 때문이다. 이걸 안 알려주면 "시세 85점"을 "상위 15%로
비싸다"로 **정반대 해석**한다. 같은 지시를 `region_explain.py`·`chat.py`에도 복사했다.

## [4] 중 — 이름이 같고 정의가 다른 백분위 함수 두 개

`to_percentile`이 `recommend.py`(427개 배열, 순위 계산용)와 `db.py`(칸+값 하나, 화면 표시용)에
각각 있었다. **둘은 진짜로 다른 함수다** — 배치용을 단건에 쓰면 매번 427개를 읽어야 하고,
단건용을 배치에 쓰면 427번 쿼리해야 한다. `dong_variants`처럼 문자 단위로 같은 사본이 아니다.

실제 값 차이는 **작았다**. `db.py` 버전이 유일하게 쓰이는 `쓰레기통_밀도`는 동점이 17개뿐이라
427개 동 중 364개가 완전히 같은 점수였고 최대 차이도 2점이었다.

그래도 고친 이유 — 두 값이 화면에서 **똑같이 "상위 N%"로 나란히 표시**된다
(`Life-Web/frontend/ui/reason.js`). 누가 이 함수를 `도서관_밀도`(동점 275개) 같은 칸에 쓰는
순간 32점씩 벌어지고, 그건 아주 자연스럽게 일어날 일이다.

**고친 것**: `db.py` 쪽을 `column_percentile()`로 개명하고(호출부 포함), 동점 규칙도
`recommend.py`와 같게 맞췄다(`<=` → `<` + 동점 절반, 분모도 `total - 1`로 통일).

## [5] 소 — `blend()` 조기 반환이 가격 키를 흘렸다 (잠복 크래시)

`if not members: return draft` — `draft`에는 지표 7개 말고도 `건물유형`(문자열)·`보증금`(None)이
들어 있어서, `recommend()`의 `sum(weights.values())`에서 `TypeError`가 난다. `member_chunk`가
900행이라 유사 회원이 항상 잡혀 지금은 안 터지지만, 재적재 중이거나 조회가 비면 검색 전체가
죽는다. [2]번 수정에서 `INDICATORS` 7개만 잘라 내보내도록 같이 해결했다.

---

## 함께 정리한 것

- **`db.py`의 `dong_variants` 중복 사본 삭제.** `a529501` 머지 충돌을 손으로 풀 때 남은 잔재로,
  `app/domain/dong.py`에서 import한 함수를 가리고 있었다. 두 사본이 문자 단위로 완전히 동일함을
  확인하고 지웠다(`import re`도 같이 불필요해짐).
- **`explain.py`의 427행 조회가 TOP 5 루프 안에 있어 요청마다 5번 반복**되던 것을 루프 밖 1회로.
- **`housing.py`에 `price_gap_text()` 신설** — 목표가 대비 방향(높음/낮음)을 문장 조각으로 만든다.
  `price_fit_score()`가 `abs()`를 쓰기 때문에 같은 "일치도 85점"이 62,000만원(싼 쪽)일 수도
  68,000만원(비싼 쪽)일 수도 있었다. 여기에 프롬프트에 목표 금액 자체를 싣는 수정을 더해,
  "원하시는 가격대보다 조금 높은 편입니다" 같은 답변이 가능해졌다.

## 아직 결론 안 난 것

**목표가 일치도를 순위에도 반영할 것인가** — 지금 `housing_fit_score()`는 후보를 추리는
필터로만 쓰이고, 그 안의 순위는 7개 지표로만 매긴다. `README.md`의 "논의 필요" 절 참고.

## 이번 점검에서 배울 것

- **조용히 틀리는 버그가 제일 비싸다.** [1]번은 예외도 경고도 안 낸다. 순위가 조금 이상할 뿐이라
  "추천이란 게 원래 애매하지" 하고 넘어가기 쉽다. 결과를 숫자로 검증하는 습관이 유일한 방어선이다.
- **정렬은 동점을 어떻게 다루는지 항상 확인해라.** 실제 데이터에는 동점이 아주 많다 — 427개 중
  275개가 같은 값이었다.
- **LLM 답변이 이상하면 모델이 아니라 프롬프트에 실제로 들어간 글을 먼저 봐라.** [3]번은
  `build_context()`의 반환값을 한 번 `print()`하면 즉시 보이는 문제였다. API 호출 없이, 비용 없이.
- **모델에게 모순된 입력을 주면 규칙보다 모순이 이긴다.** "지어내지 마라"를 아무리 세게 써도,
  가중치만 주고 점수를 안 주면 모델은 빈칸을 메운다.
- **보정·앙상블은 "무엇을 섞지 말아야 하는지"를 정하는 게 절반이다.** [2]번은 비율이 아니라
  대상이 잘못이었다. 비율만 만지면 영영 못 고친다.
- **같은 이름의 함수가 두 개면 언젠가 사고가 난다.** `dong_variants`로 한 번 겪었고
  `to_percentile`로 또 겪었다. 단, [4]번처럼 **정말 다른 함수라면 합치지 말고 이름을 나눠라** —
  합치는 게 항상 정답은 아니다.
- **스니펫의 `...`을 그대로 붙여넣으면 코드가 사라진다.** 이번에 `explain.py`가 두 번 깨졌다.
  붙여넣을 코드는 항상 완결된 블록이어야 한다.


# 17. (2026-09-04) 관리자 화면 "가입 시 희망 조건"이 전부 NaN

## 증상

회원 상세를 열면 위쪽 **가입 시 희망 조건** 블록의 슬라이더 7개가 전부 가운데에 멈춰 있고
값이 `NaN` 으로 찍힌다. 아래쪽 **현재 희망 조건**은 멀쩡하다.

## 원인 — `_초기` 칸이 DB 에 아예 없었다

`user_preferences` 표는 `data/user_preferences.csv` 를 그대로 적재해 만든다. 그런데 CSV 헤더는

```
customer_id,건물유형,거래형태,매매가,보증금,월세,건축면적,층수,준공년도,녹지,안전,교통,상권,의료,교육,문화
```

여기까지다. `녹지_초기` 같은 칸이 없다. `pipeline/schema.py` 는 **CSV 칸을 그대로 표로 옮기는**
파이프라인이라 CSV 에 없는 칸은 만들 이유가 없었다. 그런데 코드 세 곳은 그 칸이 있다고 믿고 있었다 —
`app/core/db.py` 의 `customer_preferences_initial()`, `app/features/analysis.py` 의 `facts_drift()`,
그리고 `app/features/admin.py` 의 `create_member()`.

**왜 에러가 안 났나.** 여기가 이 버그의 핵심이다. SQLite 에는 큰따옴표에 대한 관대한 예외가 있다 —
큰따옴표로 감싼 이름이 칸으로 안 잡히면 에러 대신 **문자열 리터럴로 해석한다.**

```sql
SELECT "녹지_초기" AS "녹지" FROM user_preferences;   -- 칸이 없어도 안 죽는다
```

```
('녹지_초기',)   ← 값이 아니라 칸 이름 글자가 100줄 돌아온다
```

이 글자가 JSON 을 타고 화면까지 흘러가서 `admin.html` 의 `round4()` 를 만난다.

```js
const round4 = v => (v === null || v === undefined || v === '')
  ? '' : String(Math.round(Number(v) * 1e4) / 1e4);   // Number('녹지_초기') → NaN
```

`Number('녹지_초기')` 가 `NaN` 이고, 그게 그대로 화면에 찍힌 것이다.

**같은 원인으로 조용히 틀리고 있던 곳이 하나 더 있었다.** 대시보드의 라이프스타일 변동 추이다.

```sql
SELECT COUNT(*), AVG("녹지" - "녹지_초기") FROM user_preferences
 WHERE "녹지_초기" IS NOT NULL AND ABS("녹지" - "녹지_초기") >= 0.005;
```

`"녹지_초기"` 가 글자라서 `IS NOT NULL` 은 늘 참, 뺄셈에서는 숫자 0 으로 취급된다. 결과는
`(100, 3.53)` — **"100명 전원이 평균 3.53 만큼 움직였다"** 는 그럴듯한 거짓 숫자였다.
정답은 0건이다(아직 아무도 안 고쳤으므로).

또 `create_member()` 는 `INSERT` 에 `녹지_초기` 를 넣는데, INSERT 의 칸 목록에는 저 관대한 예외가
적용되지 않아서 **관리자 화면의 "회원 추가" 는 항상 `no such column` 으로 실패하고 있었다.**

## 고친 것

**1) `pipeline/schema.py` — 적재 뒤에 파생 칸을 만든다**

CSV 에 `_초기` 7칸을 두 벌 적어 두는 대신, 적재가 끝난 시점의 값을 복사해 만든다. 적재 직후의
CSV 값이 곧 "가입 시 값"이므로 이 시점이 정확하다.

```python
# 원본 — 파생 칸 개념 자체가 없었다
    # 5. FK 칸에 색인. 조인할 때 훨씬 빨라진다
```

```python
# 수정
SNAPSHOT_SUFFIX = "_초기"
SNAPSHOT_COLUMNS = {"user_preferences": tuple(INDICATORS)}

def add_snapshot_columns(cur, table, columns, types):
    """`{칸}_초기` 칸을 만들고 지금 값을 그대로 복사한다. 이미 있으면 건너뛴다."""
    ...
    cur.execute(f'ALTER TABLE "{table}" ADD COLUMN "{snapshot}" {types.get(col, "FLOAT")}')
    cur.execute(f'UPDATE "{table}" SET "{snapshot}" = "{col}"')

# __main__ 안, 적재(4) 와 색인(5) 사이
    for name, columns in SNAPSHOT_COLUMNS.items():
        if name not in tables:
            continue
        made = add_snapshot_columns(cur, name, columns, tables[name]["type"])
```

`CREATE TABLE` 에 섞지 않고 `ALTER` 로 붙이는 이유 — CREATE 문과 INSERT 문이 **같은 칸 목록**
(`table["columns"]`, CSV 헤더)을 공유한다. 거기에 파생 칸을 끼워 넣으면 둘을 같이 고쳐야 하고,
한쪽만 고치면 "칸 수가 안 맞는다" 로 적재가 통째로 죽는다.

**2) 이미 있는 `data/life.db` 는 재적재 없이 그 자리에서 채웠다**

`python -m pipeline.schema` 는 `life.db` 를 **지우고 다시 만든다.** 그러면 CSV 에 없는 것 —
`kb_chunk`·`member_chunk` 의 벡터 900여 개, 관리자 수정 이력, 로그인 이후 쌓인 좋아요·검색·채팅 —
이 전부 날아가고 재임베딩까지 해야 한다. 그래서 방금 만든 함수를 그대로 불러 7칸만 붙였다.

```python
from pipeline.schema import add_snapshot_columns, SNAPSHOT_COLUMNS, tables
con = sqlite3.connect(DB_PATH); cur = con.cursor()
for t, cols in SNAPSHOT_COLUMNS.items():
    add_snapshot_columns(cur, t, cols, tables[t]["type"])
con.commit()
```

같은 함수를 쓴 덕에 지금 DB 와 "재적재했을 때 나올 DB" 의 스키마가 정확히 같다(둘 다 INTEGER).

**3) 조회 쪽에 "칸이 진짜 있나" 확인을 넣었다 (`db.py`, `analysis.py`)**

같은 사고가 또 나도 이번엔 **조용히 틀리지는 않게** 만든다.

```python
# app/core/db.py — 새로 추가
def table_columns(table):
    """표에 실제로 있는 칸 이름들. 없는 표면 빈 집합."""
    return {row[1] for row in query(f'PRAGMA table_info("{table}")')}
```

```python
# customer_preferences_initial() 맨 앞
if not {f"{name}_초기" for name in INDICATORS} <= table_columns("user_preferences"):
    return None          # 화면은 이 블록을 아예 안 그린다 (NaN 슬라이더 대신)
```

`facts_drift()` 도 같은 확인을 하고, 없으면 세는 시늉 대신 `"user_preferences 에 _초기 칸이 없다"`
라고 이유를 적어 돌려준다. 거짓 숫자보다 빈칸이 낫다.

## 검증

| 확인한 것 | 결과 |
| --- | --- |
| `PRAGMA table_info(user_preferences)` | `녹지_초기` … `문화_초기` 7칸 INTEGER |
| `admin.get_member("C002")` | `preferences_initial` = `{녹지:4, 안전:3, 교통:3, 상권:5, 의료:3, 교육:1, 문화:4}` — CSV 원본과 일치 |
| `_초기` 가 NULL 인 회원 | 0명 (100명 전원 채워짐) |
| `analysis.facts_drift()` | `변동_있는_칸수: 0` (고치기 전에는 거짓 100건) |
| `create_member` 의 INSERT | 성공(트랜잭션 롤백으로 확인). 고치기 전에는 `no such column` |

## 배울 것

- **SQLite 의 큰따옴표 예외를 기억해라.** 없는 칸 이름이 문자열로 둔갑한다. 오타 하나가 에러가
  아니라 "그럴듯한 값"으로 나타나는 유일한 경로다. 칸 이름을 코드로 조립할 때는(`f"{name}_초기"`)
  특히 위험하다 — 오타를 눈으로 볼 기회조차 없다.
- **"CSV 에 없는 칸"은 적재 파이프라인이 책임져야 한다.** 앱 코드가 있다고 가정만 하면 아무도
  만들지 않는다. 16절의 교훈과 같다 — 조용히 틀리는 버그가 제일 비싸다.
- **DB 를 고칠 때 재적재가 유일한 답은 아니다.** `life.db` 에는 CSV 에서 다시 만들 수 없는 것들이
  들어 있다. 칸 하나 때문에 그걸 다 버리지 말 것.

