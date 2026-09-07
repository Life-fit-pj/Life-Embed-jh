"""행정동 이름 표기 변형. 여기가 깨지면 행정동을 아예 못 찾는다."""

from app.domain.dong import dong_variants

def test_제N동_표기_없는것으로_변환():
    got = dong_variants("고덕제1동")
    assert set(got) == {"고덕제1동", "고덕1동"}


def test_제N동_표기_반대로_변환():
    got = dong_variants("고덕1동")
    assert set(got) == {"고덕제1동", "고덕1동"}


def test_숫자가_없는_이름은_그대로_출력():
    got = dong_variants("청운효자동")
    assert got == ["청운효자동"]


def test_앞뒤_공백은_없앤다():
    assert dong_variants(" 신사동 ") == ["신사동"]