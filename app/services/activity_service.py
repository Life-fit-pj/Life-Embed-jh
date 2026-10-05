"""활동(검색·좋아요)에서 회원의 성향을 정리해 관리자에게 제안한다.

제안은 저장하지 않는다 — 관리자가 화면에서 보고 고친 뒤 평소의 회원 수정(admin_service.update_member)으로 저장한다.
여기서 남기는 것은 "이런 제안을 줬다"는 기록 한 줄뿐이다(admin_log 의 target="suggestion").
그 기록이 오늘 받은 제안 목록이자 하루 횟수 제한의 근거다 — 표를 새로 만들지 않는다.
"""

import json
from datetime import datetime

from app.ai.chunker import MAX_LENGTH
from app.ai.llm import ask
from app.core.config import ACTIVITY_COLUMN, INDICATORS, MIN_LENGTH
from app.engine.weights import indicator_weights
from app.repositories.history import (
    admin_logs_of, last_change_times, list_likes, list_search_history, member_searches, write_admin_log,
)
from app.repositories.members import customer_one, customer_persona, customer_preferences
from app.engine.ranking import get_ready
from app.services import privacy_service

DAILY_LIMIT = 5             # 한 회원에게 하루에 줄 수 있는 제안 수. 누를 때마다 Claude 를 한 번 부른다
MIN_SEARCHES = 5            # 이보다 적으면 재료가 모자라 Claude 가 지어낸다
SEARCH_LIMIT = 30           # 재료로 싣는 검색어 수(최근 것부터)
SUGGESTION = "suggestion"   # admin_log 의 target. 회원 수정("member")과 구분한다
OFFERED = {ACTIVITY_COLUMN, *INDICATORS}    # 제안이 건네는 칸. 이 중 하나라도 저장했으면 그 전에 받은 제안은 쓴 것으로 본다

SYSTEM = f"""당신은 주거지 추천 서비스 LIFE,FIT 의 회원 성향을 정리합니다.
아래는 회원 한 명이 로그인한 뒤 남긴 검색어와, 좋아요를 누른 동네입니다.
이 활동에서 드러나는 주거 성향을 지표 {len(INDICATORS)}개({'·'.join(INDICATORS)}) 기준으로 정리하세요.

## 규칙
1. 근거가 있는 지표만 씁니다. 검색어나 좋아요 동네의 점수에서 드러나지 않는 지표는 아예 언급하지 않습니다. 지어내지 않습니다.
2. 성향 글은 "이 회원은"으로 시작하는 평서문 2~4문장, 300자 이내입니다. 어느 검색어·어느 동네에서 그렇게 봤는지 근거를 문장 안에 짧게 넣습니다.
3. 이름·전화·주소 같은 개인 정보는 쓰지 않습니다. 동네 이름은 써도 됩니다.
4. "지난번에 정리한 성향"이 있으면 그것을 바탕으로 하되, 새 활동에 맞게 고쳐 씁니다.
5. 가중치는 지표마다 1~5 사이 숫자(0.5 단위)입니다. 근거가 있는 지표만 지금 값에서 올리거나 내리고, 근거가 없는 지표는 지금 값을 그대로 둡니다.
6. JSON 만 출력합니다. 다른 글은 쓰지 않습니다.

{{"성향": "…", "가중치": {{{', '.join(f'"{k}": 3' for k in INDICATORS)}}}}}"""


class NotEnough(Exception):
    """재료가 모자라 제안을 못 만든다 — 검색이 MIN_SEARCHES 건 미만이거나, Claude 가 쓸 만한 글을 못 냈다"""


class LimitReached(Exception):
    """오늘 이 회원에게 줄 수 있는 제안을 다 줬다"""


def _material(queries: list, liked: list, weights: dict, previous: str) -> str:
    """Claude 에게 줄 재료 글. queries 는 가린 검색어들, liked 는 (동네, 지표 점수 글) 목록이다.

    좋아요 동네의 점수는 우리가 계산해서 준다 — Claude 에게는 숫자를 주고 해석만 시킨다
    """
    lines = [f"## 검색어 (최근 것부터 {len(queries)}건)"]
    lines += [f"- {q}" for q in queries]
    lines += ["", "## 좋아요를 누른 동네 (점수는 서울 427개 동 중 백분위)"]
    lines += [f"- {name}: {scores}" for name, scores in liked] or ["(없음)"]
    lines += ["", "## 지금 가중치 (1~5)", " / ".join(f"{k} {weights[k]:g}" for k in INDICATORS)]
    lines += ["", "## 지난번에 정리한 성향", previous or "(없음)"]
    return "\n".join(lines)


def _parse(text: str, weights: dict):
    """Claude 의 답 -> (성향 글, 가중치 7개). 못 읽으면 ("", 지금 가중치).

    가중치는 1~5 로 자른다. 지표가 빠졌거나 숫자가 아니면 지금 값을 둔다 — Claude 의 답을 그대로 믿지 않는다.
    글은 MAX_LENGTH 에서 자른다 — 넘으면 조각이 둘로 쪼개져 한 칸에 글이 둘이 된다
    """
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return "", dict(weights)
    if not isinstance(data, dict):
        return "", dict(weights)

    proposed = data.get("가중치") if isinstance(data.get("가중치"), dict) else {}
    out = {}
    for k in INDICATORS:
        v = proposed.get(k)
        ok = isinstance(v, (int, float)) and not isinstance(v, bool)
        out[k] = round(min(5.0, max(1.0, float(v))), 2) if ok else weights[k]
    return str(data.get("성향") or "").strip()[:MAX_LENGTH], out


def _as_time(text: str) -> datetime:
    """표마다 다른 시각 글자를 견줄 수 있는 값으로 바꾼다.

    search_history 는 "2026-10-02 02:59:57.972452+00"(DB 시계, UTC), admin_log 는 "2026-10-01T19:35:53"
    (서버 현지 시각, 시간대 표시 없음)이다. 글자끼리 비교하면 한국에서는 9시간이 어긋난다
    """
    return datetime.fromisoformat(text).astimezone()


def _fresh_counts(searches: list, saved: dict) -> dict:
    """회원마다 '마지막 저장 뒤에 한, 서로 다른 검색어' 수. searches 는 (회원 번호, 시각, 검색어) 목록,
    saved 는 {회원 번호: 마지막 저장 시각}.

    한 번도 저장한 적이 없는 회원은 검색 전부를 본다. 같은 검색을 여러 번 눌러도 한 건이다
    """
    last = {cid: _as_time(at) for cid, at in saved.items()}
    fresh = {}
    for cid, at, query in searches:
        if cid not in last or _as_time(at) > last[cid]:
            fresh.setdefault(cid, set()).add(query)
    return {cid: len(queries) for cid, queries in fresh.items()}


def _liked(likes: list) -> list:
    """좋아요 누른 동네마다 (이름, 지표 점수 글). 427개 동에 없는 이름은 점수 없이 이름만 준다"""
    r = get_ready()
    out = []
    for like in likes:
        name = f"{like['구']} {like['행정동명']}"
        i = r["index"].get(name)
        out.append((name, " / ".join(f"{k} {round(float(r['scores'][k][i]))}" for k in INDICATORS)
                    if i is not None else "점수 없음"))
    return out


def _unused(suggestions: list, saves: list) -> list:
    """제안 기록 중 아직 안 쓴 것. 둘 다 admin_log 의 줄({"patch", "changed_at"}) 목록이다.

    제안이 건네는 칸(활동 칸 · 가중치)을 관리자가 저장하면 그 전에 받은 제안은 쓴 것으로 본다 — 저장이 곧 승인이다.
    남겨 두면 이미 쓴 안이 새 안처럼 보인다. 이름 · 연락처만 고친 저장은 세지 않는다
    """
    used_at = max((log["changed_at"] for log in saves if OFFERED & json.loads(log["patch"]).keys()), default="")
    return [log for log in suggestions if log["changed_at"] > used_at]


def suggestions_today(customer_id: str) -> dict:
    """오늘 이 회원에게 준 제안 중 아직 안 쓴 것(받은 순)과 남은 횟수. 화면이 이 목록을 나란히 놓고 고르게 한다

    남은 횟수는 쓴 제안까지 다 센다 — 하루 한도는 받은 횟수다(누를 때마다 Claude 를 부른다)
    """
    today = datetime.now().date().isoformat()        # admin_log.changed_at 을 찍는 것과 같은 시계다
    logs = admin_logs_of(SUGGESTION, customer_id, today)
    items = [{**json.loads(log["patch"]), "created_at": log["changed_at"]}
             for log in _unused(logs, admin_logs_of("member", customer_id, today))]
    return {"suggestions": items, "remaining": max(0, DAILY_LIMIT - len(logs))}

def _generate(customer_id: str) -> dict:
    """제안 하나를 만든다(Claude 1번). 아무것도 저장하지 않는다"""
    searches = list_search_history(customer_id, SEARCH_LIMIT)
    # 가린 뒤에 중복을 걷는다 — 같은 검색을 다섯 번 눌러도 재료는 한 줄이다. 건수도 걷은 뒤의 것으로 본다
    queries = list(dict.fromkeys(privacy_service.mask_text(s["query"]) for s in searches))
    if len(queries) < MIN_SEARCHES:
        raise NotEnough(f"서로 다른 검색어가 {len(queries)}건입니다. {MIN_SEARCHES}건 이상 쌓여야 제안을 만듭니다")

    weights = indicator_weights(customer_preferences(customer_id))
    previous = customer_persona(customer_id).get(ACTIVITY_COLUMN, "")
    material = _material(queries, _liked(list_likes(customer_id)), weights, previous)

    persona, proposed = _parse(ask([("system", SYSTEM), ("human", material)], max_tokens=700), weights)
    if len(persona) < MIN_LENGTH:
        raise NotEnough("Claude 가 성향을 정리하지 못했습니다. 다시 눌러 주세요")
    return {ACTIVITY_COLUMN: persona, "가중치": proposed, "검색수": len(queries)}


def suggest(customer_id: str) -> dict | None:
    """제안을 하나 더 만들어 기록하고, 오늘 받은 제안 전부와 남은 횟수를 돌려준다. 없는 회원이면 None"""
    if customer_one(customer_id) is None:
        return None
    today = suggestions_today(customer_id)
    if today["remaining"] <= 0:
        raise LimitReached(f"오늘은 이 회원에게 제안을 {DAILY_LIMIT}번 다 받았습니다. 내일 다시 눌러 주세요")

    suggestion = _generate(customer_id)
    logged_at = write_admin_log(SUGGESTION, customer_id, suggestion)      # 받은 제안을 원문 그대로 남긴다
    # 방금 것을 붙여 돌려준다 — 기록을 다시 읽어 오면 왕복이 한 번 더 든다
    return {"suggestions": today["suggestions"] + [{**suggestion, "created_at": logged_at}],
            "remaining": today["remaining"] - 1}


def refresh_candidates() -> list:
    """성향을 갱신할 회원 — 활동 칸을 마지막으로 저장한 뒤 검색이 MIN_SEARCHES 건 이상 늘어난 회원.

    세기만 한다. Claude 를 부르지 않는다. 검색이 많이 늘어난 회원부터 준다
    """
    fresh = _fresh_counts(member_searches(), last_change_times("member", ACTIVITY_COLUMN))
    return [{"customer_id": cid, "new_searches": n}
            for cid, n in sorted(fresh.items(), key=lambda item: (-item[1], item[0])) if n >= MIN_SEARCHES]
