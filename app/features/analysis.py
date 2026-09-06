"""
관리자 분석 — DB 집계를 Claude 에게 해석시킨다.

[왜 Claude 에게 SQL 을 안 짜게 하나]
  이 파일이 SQL 로 집계표를 먼저 만들고, Claude 는 그 숫자만 읽는다.
  Claude 가 직접 쿼리를 짜게 하면 세 가지가 위험하다 —
  느린 쿼리로 서버가 멈추고, 잘못된 조인으로 틀린 숫자가 나오고,
  개인정보 칸(이름·전화·이메일)까지 긁어올 수 있다.
  집계를 우리가 만들면 그 셋 다 원천적으로 없다.

[제일 조심할 것]
  여기서 나온 답은 "회사 내부 소비자 분석 자료"로 쓰인다. 표본이 100명이고
  어떤 항목은 아직 0건인데 Claude 가 그럴듯한 이야기를 지어내면 그게 그대로
  자료가 된다. 그래서 프롬프트가 숫자를 지어내는 것을 강하게 막고,
  집계에 "표본 수"와 "왜 비어 있는지"를 같이 실어 보낸다.
"""

import json
from datetime import datetime

from app.llm import get_llm
from app.core.config import INDICATORS
from app.core.db import dicts, get_con, one, table_columns
from app.tables.history import ensure_search_history, ensure_chat_history
from app.features.admin import dashboard, pairs

# ── 집계 ────────────────────────────────────────
# 전부 (label, value) 두 칸으로 통일한다. 화면 차트 하나로 다 그릴 수 있고,
# 프롬프트에 넣을 때도 같은 방식으로 글로 바꿀 수 있다.

def facts_spread() -> dict:
    """지표마다 1~5 를 몇 명이 골랐나.

    dashboard() 는 평균만 준다. 평균 3.0 이 "다들 3점"인지 "1점과 5점이 반반"인지
    구분이 안 되므로, 판단에 필요한 분포를 여기서 따로 센다
    """
    return {
        name: pairs(
            f'SELECT CAST("{name}" AS INT), COUNT(*) FROM user_preferences '
            f'WHERE "{name}" IS NOT NULL GROUP BY 1 ORDER BY 1'
        )
        for name in INDICATORS
    }
    
    
def facts_drift() -> dict:
    """라이프스타일 변동 추이 — 가입 시 값과 지금 값의 차이.

    `_초기` 칸은 관리자 화면 작업 때 만들었다. 지금은 100명 전원이 가입 시 값
    그대로라 변동이 0건인 게 정상이다 — 그 사실을 숫자로 같이 실어 보낸다

    칸이 아예 없는 DB 면 세는 시늉을 하지 않고 그렇다고 말한다. SQLite 가
    없는 칸 이름을 문자열로 해석해 버려서, 그냥 돌리면 "100명 전원이 평균
    3.53 만큼 움직였다" 같은 그럴듯한 거짓 숫자가 나온다
    """
    if not {f"{name}_초기" for name in INDICATORS} <= table_columns("user_preferences"):
        return {
            "변동_있는_칸수": 0,
            "지표별_평균변화": [],
            "비어있는_이유": "user_preferences 에 `_초기` 칸이 없다. "
                             "python -m pipeline.schema 로 다시 적재해야 생긴다",
        }

    changed, moves = 0, []
    for name in INDICATORS:
        row = one(
            f'SELECT COUNT(*), AVG("{name}" - "{name}_초기") FROM user_preferences '
            f'WHERE "{name}_초기" IS NOT NULL AND ABS("{name}" - "{name}_초기") >= 0.005'
        )
        n, delta = (row or (0, None))
        changed += n or 0
        if n:
            moves.append({"label": name, "value": round(delta, 3), "인원": n})

    return {
        "변동_있는_칸수": changed,
        "지표별_평균변화": moves,
        "비어있는_이유": None if changed else
            "아직 아무도 가입 시 값에서 바뀌지 않았다. 관리자가 회원 가중치를 "
            "고치거나 회원이 설문을 다시 하면 여기에 쌓인다",
    }


def facts_searches(top=20) -> dict:
    """검색어 트렌드 — 로그인 담당이 만든 search_history / chat_history 를 읽는다.

    표 구조는 손대지 않는다. `anon_id` 한 칸을 겸용하는 설계지만(로그인하면 그 자리에
    customer_id 가 들어간다) 여기서는 "누가"가 아니라 "무엇을 많이 찾았나"만 세므로
    그대로 읽으면 된다
    """
    ensure_search_history()      # ← 팀원 함수를 그대로 부른다 (1-2에서 import 함)
    ensure_chat_history()

    total = one("SELECT COUNT(*) FROM search_history")[0]
    return {
        "검색_건수": total,
        "많이_찾은_말": pairs(
            "SELECT query, COUNT(*) FROM search_history GROUP BY 1 "
            "ORDER BY 2 DESC LIMIT ?", (top,)
        ),
        "대화_건수": one("SELECT COUNT(*) FROM chat_history")[0],
        "비어있는_이유": None if total else
            "아직 아무도 검색하지 않았다. 사용자가 검색창을 쓰면 여기에 쌓인다",
    }


def collect_facts() -> dict:
    """화면(대시보드)이 쓰는 집계를 그대로 가져오고, 없는 것만 더한다.

    ⚠ dashboard() 를 재사용하는 이유는 줄 수가 아니라 "숫자가 어긋나지 않게" 하려는 것이다.
      따로 계산하면 차트는 3.53 인데 답변은 3.2 인 일이 생긴다.
      대신 dashboard() 를 고치면 Claude 가 보는 것도 같이 바뀐다는 걸 알고 고칠 것
    """
    d = dashboard()
    return {
        "규모": d["counts"],
        "회원_성향": {
            # ⚠ 표본은 counts["members"] 가 아니다 —
            #   그건 customers 표(로그인만 발급된 빈 계정 포함)라 가중치가 없는 사람까지 센다
            "표본": one("SELECT COUNT(*) FROM user_preferences")[0],
            "지표평균": d["charts"]["weights"],
            "지표분포": facts_spread(),
            "연령대": d["charts"]["ages"],
            "성별": d["charts"]["genders"],
            "가입추이": d["charts"]["joins"],
            "희망거래형태": d["charts"]["dealType"],
        },
        "지역_수요": {
            "거주_자치구": d["charts"]["memberGu"],
            "직장_자치구": pairs(
                "SELECT work_city, COUNT(*) FROM customers WHERE work_city IS NOT NULL "
                "GROUP BY 1 ORDER BY 2 DESC LIMIT 15"),
            "좋아요_동네": pairs(
                "SELECT 구 || ' ' || 행정동명, COUNT(*) FROM likes "
                "GROUP BY 1 ORDER BY 2 DESC LIMIT 15"),
        },
        "변동_추이": facts_drift(),
        "검색_트렌드": facts_searches(),
    }


# ── Claude 에게 묻기 ─────────────────────────────

SYSTEM = """당신은 주거 추천 서비스 LIFE,FIT 의 데이터 분석 도우미입니다.
아래 "집계 자료"만 보고 관리자의 질문에 답하세요.

## 반드시 지킬 것

1. 집계 자료에 있는 숫자만 쓰세요. 없는 숫자를 추정하거나 지어내지 마세요.
2. 자료에 없는 것을 물으면 "그 자료는 아직 없습니다"라고 답하고,
   무엇이 있어야 답할 수 있는지 한 줄로 알려주세요.
3. `비어있는_이유`가 채워진 항목은 데이터가 없는 것입니다.
   그 이유를 그대로 전하고, 없는 데이터로 추세를 말하지 마세요.
4. 표본 수를 반드시 밝히세요. 회원 100명은 작은 표본입니다.
   "회원들은 ~하다" 대신 "회원 100명 표본에서는 ~로 나타난다"로 쓰세요.
5. 이 답변은 회사 내부 자료로 쓰입니다. 확실하지 않으면 확실하지 않다고 쓰세요.

한국어로, 짧게. 숫자를 인용할 때는 항목 이름을 같이 쓰세요."""


def _facts_text(facts: dict) -> str:
    """집계를 Claude 가 읽을 글로. JSON 을 그대로 넣는 게 가장 오해가 적다."""
    return json.dumps(facts, ensure_ascii=False, indent=1)


def ask(question: str) -> dict:
    """질문 하나에 답하고 기록에 남긴다."""
    question = (question or "").strip()
    if not question:
        return {"error": "질문이 비어 있다"}

    facts = collect_facts()
    prompt = f"## 집계 자료\n{_facts_text(facts)}\n\n## 질문\n{question}"
    answer = get_llm(max_tokens=900).invoke(
        [("system", SYSTEM), ("human", prompt)]).content.strip()

    chat_id = save_chat(question, answer, facts)
    return {"chat_id": chat_id, "question": question, "answer": answer, "facts": facts}


# ── 대화 보관 ────────────────────────────────────

_ready = False


def ensure_table():
    """분석 대화 표가 없으면 만든다. likes·history 와 같은 방식이다."""
    global _ready
    if _ready:
        return
    get_con().execute("""
        CREATE TABLE IF NOT EXISTS analysis_chat (
            chat_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            question   TEXT NOT NULL,
            answer     TEXT,
            facts      TEXT,
            created_at TEXT
        )
    """)
    get_con().commit()
    _ready = True


def save_chat(question, answer, facts) -> int:
    """질문·답과 함께 그때의 집계를 통째로 남긴다.

    집계까지 남기는 이유 — 데이터는 계속 바뀐다. 한 달 뒤 이 답을 다시 열었을 때
    "그때는 무슨 숫자를 보고 이렇게 답했나"를 알 수 없으면 답을 믿을 수 없다
    """
    ensure_table()
    con = get_con()
    cur = con.execute(
        "INSERT INTO analysis_chat (question, answer, facts, created_at) VALUES (?, ?, ?, ?)",
        (question, answer, json.dumps(facts, ensure_ascii=False),
         datetime.now().isoformat(timespec="seconds")),
    )
    con.commit()
    return cur.lastrowid


def list_chats(limit=50) -> list:
    """저장된 분석 대화 목록. 목록에는 답을 짧게만 싣는다."""
    ensure_table()
    rows = dicts(
        "SELECT chat_id, question, substr(answer, 1, 90) AS preview, created_at "
        "FROM analysis_chat ORDER BY chat_id DESC LIMIT ?", (limit,)
    )
    return rows


def get_chat(chat_id: int) -> dict | None:
    """대화 하나를 통째로. 그때의 집계도 같이 돌려준다."""
    ensure_table()
    rows = dicts(
        "SELECT chat_id, question, answer, facts, created_at "
        "FROM analysis_chat WHERE chat_id = ?", (chat_id,)
    )
    if not rows:
        return None
    row = rows[0]
    try:
        row["facts"] = json.loads(row["facts"]) if row["facts"] else None
    except json.JSONDecodeError:
        row["facts"] = None
    return row


def delete_chat(chat_id: int) -> int:
    ensure_table()
    con = get_con()
    n = con.execute("DELETE FROM analysis_chat WHERE chat_id = ?", (chat_id,)).rowcount
    con.commit()
    return n
