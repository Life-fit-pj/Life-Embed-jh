"""긴 글 쪼개기. 글자가 하나라도 버려지면 관리자가 저장할 때 조용히 사라진다."""

from app.ai.chunker import MAX_LENGTH, MEMBER_KEYS, make_chunks, split_long_text
from app.core.config import MIN_LENGTH

# 가입 설문 답처럼 짧은 문장과 긴 문장이 섞인 글
SURVEY = ("집에서 버스로 출퇴근 합니다. 집에서 쉽니다. 집 앞 공원이나 헬스장에서 운동합니다. 실내 활동이 편합니다. "
          "집에서 애니메이션 보거나 게임합니다. 사람이 적고 자연적인 곳. 매일 산속에서 런닝을 뜁니다. "
          "사람이 적은 경치좋은곳 렌터카 빌려서 다닙니다. 주로 직접 해먹습니다. 동네 근처에 고기집이 있다면 자주 갑니다. "
          "아내와 둘이 살고 곧 아이를 가질 예정입니다. 화장실이 1개인 점이 아쉬워요 시골같이 조용한 곳에 자랐습니다. "
          "평택이 조용하고 재해도 없어서 좋았습니다. 주말에는 근교 캠핑장을 찾아 다니는 편이고 차를 오래 타는 것도 괜찮습니다. "
          "아이가 생기면 어린이집과 소아과가 가까운 곳이 좋겠다고 생각하고 있습니다. 마트는 일주일에 한 번 차로 다녀옵니다.")


def test_짧은_글은_그대로다():
    assert split_long_text("짧은 문장입니다.") == ["짧은 문장입니다."]


def test_긴_글은_이어_붙이면_원래_글이_된다():
    pieces = split_long_text(SURVEY)
    assert len(pieces) > 1
    assert " ".join(pieces) == SURVEY          # 짧은 문장도 하나도 안 버려진다


def test_조각은_너무_짧지도_너무_길지도_않다():
    for piece in split_long_text(SURVEY * 2):
        assert MIN_LENGTH <= len(piece) <= MAX_LENGTH + MIN_LENGTH


def test_마침표_없이_긴_글도_글자를_안_버린다():
    text = "마침표없이계속이어쓴글" * 70                  # 770자, 문장이 하나다
    pieces = split_long_text(text)
    assert "".join(pieces).replace(" ", "") == text
    assert all(len(piece) >= MIN_LENGTH for piece in pieces)


def test_청크로_만들어도_글이_다_남는다():
    chunks = make_chunks([{"customer_id": "C000", "persona": SURVEY}], MEMBER_KEYS)
    assert {c["category"] for c in chunks} == {"persona"}
    assert " ".join(c["text"] for c in chunks) == SURVEY
