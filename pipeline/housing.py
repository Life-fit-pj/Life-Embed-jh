"""
할 일 : 건물유형·거래유형·목표가 조건에 맞는 동을 추리고, 목표가와 얼마나 가까운지 점수를 매긴다.

기존 7개 지표와 다르게 "많고 적음"이 아니라 "사용자가 정한 숫자와 얼마나 가까운가"를 보는
필터다. master_dataset_v3 에 이미 (건물유형, 거래유형) 별 시세가 동마다 한 줄로 있으므로
새 표를 만들 필요 없이 여기서 바로 걸러낸다.
"""

from app.core.db import region_densities, region_price_detail

# {건물유형}_{거래유형}_{금액종류} 규칙 그대로 매핑한다.
# 매매·전세는 금액이 하나("예산")뿐이지만, 월세는 다르다 — 보증금(목돈)과 월세(매달 나가는 돈)가
# 따로 있고, 사용자가 실질적으로 더 신경 쓰는 건 월세 쪽이다. 그래서 월세 거래에서는 "예산"을
# 월세 칼럼에 매핑하고, 보증금은 있으면 참고하는 보조 조건(secondary)으로 따로 받는다.
DEAL_COLUMNS = {
    ("단독다가구", "매매"): {"예산": "단독다가구_매매_매매가"},
    ("아파트",     "매매"): {"예산": "아파트_매매_매매가"},
    ("연립다세대", "매매"): {"예산": "연립다세대_매매_매매가"},
    ("오피스텔",   "매매"): {"예산": "오피스텔_매매_매매가"},

    ("단독다가구", "전세"): {"예산": "단독다가구_전세_보증금"},
    ("아파트",     "전세"): {"예산": "아파트_전세_보증금"},
    ("연립다세대", "전세"): {"예산": "연립다세대_전세_보증금"},
    ("오피스텔",   "전세"): {"예산": "오피스텔_전세_보증금"},

    ("단독다가구", "월세"): {"예산": "단독다가구_월세_월세", "보증금": "단독다가구_월세_보증금"},
    ("아파트",     "월세"): {"예산": "아파트_월세_월세",     "보증금": "아파트_월세_보증금"},
    ("연립다세대", "월세"): {"예산": "연립다세대_월세_월세", "보증금": "연립다세대_월세_보증금"},
    ("오피스텔",   "월세"): {"예산": "오피스텔_월세_월세",   "보증금": "오피스텔_월세_보증금"},
}

# 필드별 가중치. "월세가 보증금보다 더 중요한 지표"라는 기준을 숫자로 표현한 것이다.
# 매매·전세는 필드가 "예산" 하나뿐이라 이 가중치가 어차피 안 쓰인다.
FIELD_WEIGHT = {"예산": 0.7, "보증금": 0.3}


def price_fit_score(price, target, tolerance=0.3):
    """목표값 하나와 얼마나 가까운지 0~100점으로 매긴다.

    100 = 목표값과 정확히 일치. tolerance(기본 30%)만큼 벗어나면 0점.
    너무 싸도(-30%) 너무 비싸도(+30%) 똑같이 감점되는 대칭 구조다 —
    "저렴할수록 무조건 좋다"가 아니라 "목표값에서 벗어날수록 안 좋다"는 뜻이라서다.
    matching_regions() 의 tolerance 와 같은 값을 써야 앞뒤가 맞는다.
    """
    if price is None or target in (None, 0):
        return None
    diff_ratio = abs(price - target) / target
    return max(0, round(100 * (1 - diff_ratio / tolerance)))


def housing_fit_score(row, cols, targets, tolerance=0.3):
    """한 동네가 사용자 조건(들)과 얼마나 맞는지 0~100점으로 합친다.

    cols: DEAL_COLUMNS[(건물유형, 거래유형)] 처럼 {"예산": 칼럼명} 또는
          {"예산": 칼럼명, "보증금": 칼럼명}(월세) 형태.
    targets: 사용자가 실제로 입력한 값. {"예산": 70} 또는 {"예산": 70, "보증금": 5000}.

    필드가 하나면(매매·전세) price_fit_score 하나만 쓰는 것과 같은 결과다.
    필드가 둘이면(월세) FIELD_WEIGHT 로 가중 평균한다 — 월세가 보증금보다 크게 반영된다.
    """
    total_w, total_score = 0, 0
    for field, col in cols.items():
        target = targets.get(field)
        if target is None:
            continue
        score = price_fit_score(row.get(col), target, tolerance)
        if score is None:
            continue
        w = FIELD_WEIGHT.get(field, 1.0)
        total_score += score * w
        total_w += w
    return round(total_score / total_w) if total_w else None


def matching_regions(건물유형, 거래유형, targets, tolerance=0.3, fallback=20):
    """조건(들)에 맞는 동 이름("구 동" 형태) 목록을 돌려준다.

    targets 예시: {"예산": 65000}                    매매·전세
                {"예산": 70, "보증금": 5000}          월세 (예산=월세, 보증금은 옵션)

    후보가 너무 적으면(5개 미만) 종합 점수(housing_fit_score)가 가장 높은 fallback 개를
    대신 돌려준다 — "이 조건엔 맞는 곳이 없다"고 빈 결과를 주는 것보다, 대안을 보여주는 쪽이 낫다.
    """
    cols = DEAL_COLUMNS.get((건물유형, 거래유형))
    if not cols:
        return []

    rows = region_densities(list(cols.values()))
    scored = [(r, housing_fit_score(r, cols, targets, tolerance)) for r in rows]
    scored = [(r, s) for r, s in scored if s is not None]

    candidates = [r for r, s in scored if s > 0]   # tolerance 안에 조금이라도 걸치는 동
    if len(candidates) < 5:
        candidates = [r for r, s in sorted(scored, key=lambda x: -x[1])[:fallback]]

    return [f"{r['구']} {r['행정동명']}" for r in candidates]


def _format_price_note(detail):
    """신뢰등급·거래건수·분포(상하위 25~75%)를 괄호 문장 조각으로 만든다.

    detail 은 region_price_detail() 의 결과(dict 또는 None)다. 시세_지역별_전처리에
    그 조합이 아예 없으면 detail 이 None 이라 빈 문자열을 돌려준다 — 그러면 호출부에서
    그냥 아무것도 안 붙은 것처럼 자연스럽게 문장이 끝난다.
    """
    if not detail:
        return ""

    bits = []
    if detail.get("신뢰등급"):
        bits.append(f"신뢰 {detail['신뢰등급']}")
    if detail.get("거래건수") is not None:
        bits.append(f"거래 {detail['거래건수']}건")

    # 매매는 매매가_25/75, 전세·월세는 보증금_25/75 — 월세엔 이 칼럼 자체가 없다
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
    """동네·건물유형·거래유형 하나에 대한 신뢰등급·거래건수·분포를 문장 조각으로 돌려준다.

    시세_지역별_전처리에 그 조합이 없으면(예: 표본 자체가 없는 동) 빈 문자열이다.
    """
    return _format_price_note(region_price_detail(gu, dong, 건물유형, 거래유형))


def region_price_lines(gu, dong):
    """동네 하나의 시세 전부를 건물유형별 한 줄씩 문장으로 만든다.

    housing_fit_score() 와 다르게 목표가와 비교하지 않는다 — chat.py 처럼 사용자가 어떤
    조건("월세 얼마야?")을 물어볼지 미리 모르는 곳에서, 있는 그대로의 값을 전부 보여주고
    Claude 가 질문에 맞는 걸 골라 답하게 하려는 용도다.

    금액 뒤엔 그 (건물유형, 거래유형) 조합의 신뢰등급·거래건수·분포를 괄호로 덧붙인다 —
    "매매 95,250만원" 만으로는 표본이 42건인지 2건인지 알 수 없어서다.
    """
    all_cols = sorted({col for cols in DEAL_COLUMNS.values() for col in cols.values()})
    rows = region_densities(all_cols)
    row = next((r for r in rows if r["구"] == gu and r["행정동명"] == dong), None)
    if row is None:
        return []

    lines = []
    for 건물유형 in ("단독다가구", "아파트", "연립다세대", "오피스텔"):
        parts = []
        for 거래유형 in ("매매", "전세", "월세"):
            cols = DEAL_COLUMNS.get((건물유형, 거래유형))
            if not cols:
                continue
            note = region_price_note(gu, dong, 건물유형, 거래유형)
            for field, col in cols.items():
                value = row.get(col)
                if value is None:
                    continue
                # "예산" 필드는 그 거래유형 자체를 라벨로 쓴다 (매매가→매매, 보증금→전세, 월세→월세)
                label = 거래유형 if field == "예산" else field
                # 신뢰등급·거래건수·분포는 거래유형 단위 정보라 "예산" 필드 하나에만 붙인다
                # (보증금·월세 두 필드가 각각 note를 달면 같은 정보가 중복돼 문장이 지저분해진다)
                suffix = note if field == "예산" else ""
                parts.append(f"{label} {value:,.0f}만원{suffix}")
        if parts:
            lines.append(f"{건물유형}: " + " · ".join(parts))
    return lines


def attach_price(detailed, housing):
    """detailed(동네별 dict 목록)에 그 동네의 시세를 구조화된 값으로 붙인다.

    explain.py/region_explain.py/chat.py 는 시세를 "문장"으로만 만들어 프롬프트에
    넣는데, 화면(예: 주변 시세 탭)에 표로 보여주려면 숫자 그대로도 필요하다.

    housing 이 없으면(가격 조건 없이 검색한 경우) d["price"] 는 전부 None 이다.
    """
    if not housing:
        for d in detailed:
            d["price"] = None
        return detailed

    cols = DEAL_COLUMNS.get((housing["건물유형"], housing["거래유형"]))
    if not cols:
        for d in detailed:
            d["price"] = None
        return detailed

    rows = region_densities(list(cols.values()))
    by_name = {f"{r['구']} {r['행정동명']}": r for r in rows}

    for d in detailed:
        row = by_name.get(d["name"])
        if row is None:
            d["price"] = None
            continue

        gu, dong = d["name"].split(" ", 1)
        detail = region_price_detail(gu, dong, housing["건물유형"], housing["거래유형"])

        d["price"] = {
            "건물유형": housing["건물유형"],
            "거래유형": housing["거래유형"],
            **{field: row.get(col) for field, col in cols.items()},   # 중앙값 (master_dataset_v3)
            "일치도": housing_fit_score(row, cols, housing["targets"]),
            # 신뢰도·분포 정보. 시세_지역별_전처리에 그 조합이 없으면 전부 None
            "거래건수": (detail or {}).get("거래건수"),
            "신뢰등급": (detail or {}).get("신뢰등급"),
            "출처": (detail or {}).get("출처"),
            "금액_25": (detail or {}).get("매매가_25") or (detail or {}).get("보증금_25"),
            "금액_75": (detail or {}).get("매매가_75") or (detail or {}).get("보증금_75"),
        }
    return detailed
