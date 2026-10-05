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




def test_번호_사이_마침표는_가운뎃점으로도_만든다():
    # master 는 '상계6.7동', 학원·의료 표는 '상계6·7동' — 이걸 몰라 학원 440곳이 못 붙었다
    assert "상계6·7동" in dong_variants("상계6.7동")


def test_번호_사이_가운뎃점은_마침표로도_만든다():
    assert "종로1.2.3.4가동" in dong_variants("종로1·2·3·4가동")


def test_제와_점이_같이_있어도_잇는다():
    # master '면목제3.8동' ↔ 학원 표 '면목3·8동' — '제' 를 떼고 점도 바꿔야 만난다
    assert "면목3·8동" in dong_variants("면목제3.8동")

