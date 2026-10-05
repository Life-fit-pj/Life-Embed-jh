"""활동에서 본 성향 — 순수 계산만. DB 도 Claude 도 안 부른다."""

from app.services.activity_service import _as_time, _fresh_counts, _material, _parse, _unused

WEIGHTS = {"녹지": 3.0, "안전": 3.0, "교통": 3.0, "상권": 3.0, "의료": 3.0, "교육": 4.0, "문화": 2.5}


def test_가중치는_1에서_5_사이로_자른다():
    _, out = _parse('{"성향": "이 회원은 학원이 많은 동네를 찾는다.", "가중치": {"교육": 9, "녹지": 0}}', WEIGHTS)
    assert out["교육"] == 5.0 and out["녹지"] == 1.0


def test_빠졌거나_숫자가_아닌_지표는_지금_값을_둔다():
    _, out = _parse('{"성향": "이 회원은 학원이 많은 동네를 찾는다.", "가중치": {"교육": "높게", "안전": true}}', WEIGHTS)
    assert out == WEIGHTS


def test_못_읽는_답은_빈_제안이다():
    assert _parse("죄송하지만 정리할 수 없습니다", WEIGHTS) == ("", WEIGHTS)
    assert _parse('["목록"]', WEIGHTS) == ("", WEIGHTS)


def test_코드_울타리가_붙어_와도_읽는다():
    text, _ = _parse('```json\n{"성향": "이 회원은 공원이 가까운 동네를 찾는다.", "가중치": {}}\n```', WEIGHTS)
    assert text == "이 회원은 공원이 가까운 동네를 찾는다."


def test_글은_한_조각_길이에서_자른다():
    text, _ = _parse('{"성향": "' + "가" * 500 + '", "가중치": {}}', WEIGHTS)
    assert len(text) == 350


def test_재료에_검색어와_좋아요와_지금_가중치가_실린다():
    material = _material(["학원 많은 동네", "공원 가까운 곳"], [("관악구 서원동", "녹지 12 / 교육 80")], WEIGHTS, "")
    assert "- 학원 많은 동네" in material
    assert "- 관악구 서원동: 녹지 12 / 교육 80" in material
    assert "교육 4 / 문화 2.5" in material
    assert material.endswith("(없음)")          # 지난번 성향이 없을 때


def test_좋아요가_없으면_없다고_적는다():
    assert "(없음)" in _material(["학원 많은 동네"], [], WEIGHTS, "이 회원은 학원을 찾는다.").split("## 지금 가중치")[0]


def test_두_표의_시각을_같은_시계로_견준다():
    # 검색은 DB 시계(UTC), 저장 기록은 서버 현지 시각이다. 같은 순간이면 같아야 한다
    utc = _as_time("2026-10-02 02:59:57+00")
    assert utc == _as_time(utc.astimezone().replace(tzinfo=None).isoformat())


def test_마지막_저장_뒤의_서로_다른_검색어만_센다():
    saved_at = _as_time("2026-10-02 03:00:00+00").astimezone().replace(tzinfo=None).isoformat()   # 서버 현지 시각 글자
    searches = [("C102", "2026-10-02 02:00:00+00", "학원 많은 동네"),      # 저장 전
                ("C102", "2026-10-02 04:00:00+00", "공원 가까운 곳"),      # 저장 뒤
                ("C102", "2026-10-02 05:00:00+00", "공원 가까운 곳"),      # 같은 검색을 또 — 한 건으로 센다
                ("C107", "2026-10-01 01:00:00+00", "역세권")]              # 한 번도 저장 안 한 회원
    assert _fresh_counts(searches, {"C102": saved_at}) == {"C102": 1, "C107": 1}


def test_제안이_건네는_칸을_저장하면_그_전_제안은_쓴_것이다():
    suggestions = [{"patch": "{}", "changed_at": "2026-10-05T12:25:17"},
                   {"patch": "{}", "changed_at": "2026-10-05T16:56:25"},
                   {"patch": "{}", "changed_at": "2026-10-05T17:30:00"}]
    saves = [{"patch": '{"교통": 4.5, "activity_persona": "이 회원은"}', "changed_at": "2026-10-05T16:56:41"}]
    assert [s["changed_at"] for s in _unused(suggestions, saves)] == ["2026-10-05T17:30:00"]


def test_이름만_고친_저장은_제안을_쓴_것으로_안_본다():
    suggestions = [{"patch": "{}", "changed_at": "2026-10-05T12:25:17"}]
    saves = [{"patch": '{"name": "홍길동", "phone": "010"}', "changed_at": "2026-10-05T13:00:00"}]
    assert _unused(suggestions, saves) == suggestions
    assert _unused(suggestions, []) == suggestions
