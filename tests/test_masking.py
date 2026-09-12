"""
'제 번호는 010-1234-5678 이에요'          -> '제 번호는 [연락처] 이에요'
'메일은 abc.d@example.com 입니다'          -> '메일은 [메일] 입니다'
'저는 김민수입니다'      names=['김민수']  -> '저는 [이름]입니다'
'김민수와 김민이 왔다'   names=['김민','김민수'] -> '[이름]와 [이름]이 왔다'
'카톡 아이디 abc123 으로 주세요. 그리고 반가워요.' -> '그리고 반가워요.'
''                                         -> ''
build_address_pattern([], [])              -> None
'강남구 역삼1동에 살아요'  address=위 패턴  -> '[주소] [주소]에 살아요'
"""
"""나가는 글에서 개인정보를 가린다. 여기가 깨지면 개인정보가 샌다."""

from app.ai.masking import build_address_pattern, mask


def test_휴대폰_번호를_가린다():
    assert mask("제 번호는 010-1234-5678 이에요") == "제 번호는 [연락처] 이에요"


def test_메일을_가린다():
    assert mask("메일은 abc.d@example.com 입니다") == "메일은 [메일] 입니다"


def test_이름을_가린다():
    assert mask("저는 김민수입니다", names=["김민수"]) == "저는 [이름]입니다"


def test_긴_이름부터_지운다():
    # '김민' 을 먼저 지우면 '김민수' 가 '[이름]수' 가 되어 한 글자가 남는다
    got = mask("김민수와 김민이 왔다", names=["김민", "김민수"])
    assert got == "[이름]와 [이름]이 왔다"
    assert "수" not in got


def test_연락_수단이_적힌_문장은_통째로_걷어낸다():
    got = mask("카톡 아이디 abc123 으로 주세요. 그리고 반가워요.")
    assert got == "그리고 반가워요."


def test_빈_글은_그대로_돌려준다():
    assert mask("") == ""


def test_목록이_비면_주소_패턴을_안_만든다():
    assert build_address_pattern([], []) is None


def test_자치구와_행정동을_가린다():
    address = build_address_pattern(["강남구", "중구"], ["역삼1동"])
    assert mask("강남구 역삼1동에 살아요", address=address) == "[주소] [주소]에 살아요"
