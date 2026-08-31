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
  신뢰등급·거래건수·분포를 문장으로 만들어 Claude에게 넘긴다(신뢰등급·거래건수·분포는
  2026-08-31에 추가 — 아래 "14." 참고).
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

---

# 14. (2026-08-31) 신뢰등급·거래건수·분포를 LLM 프롬프트 텍스트에도 노출

## 문제

`attach_price()`는 `d["price"]`에 신뢰등급·거래건수·금액_25/75(분포)를 구조화된 값으로 이미
담고 있었다. 그런데 이건 프론트엔드가 화면에 표로 그릴 때 쓰는 값이고, **Claude에게 넘기는
프롬프트 문장에는 안 들어가 있었다.** `explain.py`/`region_explain.py`/`chat.py` 세 곳 다
시세를 "문장"으로 만들 때 중앙값(`master_dataset_v3`)과 `housing_fit_score()`(조건 일치도)만
썼다 — 신뢰등급·거래건수·분포는 계산은 해뒀는데 Claude가 설명문이나 챗봇 답변에서 실제로
언급할 방법이 없었던 것.

## 고친 것 — `pipeline/housing.py`에 문장 조각 만드는 함수 추가

```python
# pipeline/housing.py (추가)
def _format_price_note(detail):
    """신뢰등급·거래건수·분포(상하위 25~75%)를 괄호 문장 조각으로 만든다."""
    if not detail:
        return ""
    bits = []
    if detail.get("신뢰등급"):
        bits.append(f"신뢰 {detail['신뢰등급']}")
    if detail.get("거래건수") is not None:
        bits.append(f"거래 {detail['거래건수']}건")

    lo = detail.get("매매가_25")
    hi = detail.get("매매가_75")
    if lo is None or hi is None:
        lo, hi = detail.get("보증금_25"), detail.get("보증금_75")
    if lo is not None and hi is not None:
        bits.append(f"분포 {lo:,.0f}~{hi:,.0f}만원")

    if detail.get("출처") and detail["출처"] != "해당지역":
        bits.append(f"{detail['출처']} 값 대체")

    return f" ({' · '.join(bits)})" if bits else ""


def region_price_note(gu, dong, 건물유형, 거래유형):
    """동네·건물유형·거래유형 하나의 신뢰등급·거래건수·분포를 문장 조각으로 돌려준다."""
    return _format_price_note(region_price_detail(gu, dong, 건물유형, 거래유형))
```

`region_price_detail()`은 `app/core/db.py`에 이미 만들어져 있던 걸 그대로 재사용한다 — 새
쿼리 방식을 따로 안 만들었다.

## 세 호출부에 붙이기

`explain.py`/`region_explain.py`는 "참고 시세" 줄을 만드는 곳에서 `housing_fit_score()` 뒤에
`region_price_note(gu, dong, housing["건물유형"], housing["거래유형"])`를 한 번 더 불러 문장
끝에 붙였다.

```python
# pipeline/explain.py (build_context(), housing 블록 — 수정)
fit = housing_fit_score(row, cols, housing["targets"])
parts = [f"{field} {row[col]:,.0f}만원" for field, col in cols.items()]
note = region_price_note(gu, dong, housing["건물유형"], housing["거래유형"])
lines.append(f"{d['name']}: {housing['건물유형']} {housing['거래유형']} " +
             " / ".join(parts) + f" (조건 일치도 {fit}점){note}")
```

`chat.py`가 쓰는 `region_price_lines()`는 동네 하나당 최대 12개(건물유형4×거래유형3) 조합을
다 보여주므로, "예산" 필드(매매가→매매, 보증금→전세, 월세→월세) 하나에만 note를 붙였다 —
보증금·월세 두 필드가 각각 붙이면 같은 정보가 중복돼 문장이 지저분해지기 때문이다.

결과 예시(`region_price_lines("노원구", "중계1동")`):

```
아파트: 매매 82,000만원 (신뢰 높음 · 거래 289건 · 분포 60,000~118,000만원) ·
        전세 50,000만원 (신뢰 높음 · 거래 317건 · 분포 34,000~68,000만원) ·
        월세 86만원 (신뢰 높음 · 거래 238건) · 보증금 5,000만원
```

## SYSTEM_PROMPT도 같이 고쳤다

문장에 신뢰등급·거래건수·분포가 새로 나타나는데 Claude에게 그게 뭔지, 어떻게 다뤄야 하는지
설명이 없으면 무시하거나 엉뚱하게 해석할 수 있다. 세 파일 SYSTEM_PROMPT에 공통으로 추가한
내용:

> 괄호로 신뢰등급·거래건수·분포가 붙어 있으면 참고하세요 — 거래건수가 적거나 신뢰등급이
> 낮으면 표본이 적어 참고용이라고 밝히세요.

`explain.py`엔 분포 해석 방법("실제 매물 가격이 그 폭 안에 퍼져 있다는 뜻")도 한 줄 더
추가했다. `region_explain.py`는 원래 "시세" 관련 지침이 SYSTEM_PROMPT에 아예 없던 걸 이번에
같이 채워 넣었다(중앙값·실제 매물가 아님·신뢰등급 안내를 규칙 4에 추가).

## 검증

`region_price_note()`, `region_price_lines()`, `explain.build_context()`,
`region_explain.build_context()`를 노원구 중계1동으로 직접 돌려 확인함 — 신뢰등급·거래건수·
분포·출처(자치구/법정동 값 대체 여부)가 전부 문장에 정상적으로 붙는다. `attach_price()`
(구조화된 값)는 이번에 안 건드렸다 — 이미 같은 정보를 갖고 있었으므로 중복 작업이 아니라
문장 표현 계층 하나만 추가한 것이다.

## 주의할 점

- **`region_price_note()`는 `region_price_lines()` 안에서 조합마다 새로 쿼리한다.**
  `chat.py`는 동네 하나당 최대 12번(4건물유형×3거래유형 중 값이 있는 조합만) 호출한다 — TOP5
  규모(최대 60쿼리/요청)에선 문제없지만, 호출이 훨씬 잦아지면 `region_densities()` 캐싱과
  같은 방식으로 최적화할 수 있다.
- **`출처`가 "해당지역"이면 note에서 아예 생략한다.** 그 동네 자체 표본이 있다는 뜻이라
  따로 알릴 필요가 없어서다. "자치구"/"법정동" 값으로 대체된 경우만 문장에 남긴다.
- **월세는 분포가 항상 빠진다.** 위 "여전히 유효한 주의사항"에 적어둔 원본 데이터 한계가
  그대로 적용된다.
