"""밖으로 내보내기 전에 개인정보를 가린다.

DB도 네트워크도 모르는 순수 함수만 둔다 (dong.py 와 같은 계층).
이름 목록은 밖에서 받는다 — 이 파일이 customers 표를 알면 안 된다.

한계를 먼저 적어 둔다: 완벽하게 못 막는다.
목표는 "실수로 통째로 흘러나가는 것"을 막는 것이다.
"""

import re

# 휴대폰(010-1234-5678, 01012345678, 010.1234.5678)
MOBILE = re.compile(r"01[016-9][-.\s]?\d{3,4}[-.\s]?\d{4}")
# 지역번호 유선(02-123-4567, 031-1234-5678)
LANDLINE = re.compile(r"0(?:2|[3-6][1-5])[-.\s]?\d{3,4}[-.\s]?\d{4}")
# 국제 표기(+82-10-1234-5678)
INTL = re.compile(r"\+82[-.\s]?1?0?[-.\s]?\d{3,4}[-.\s]?\d{4}")

PHONE_PATTERNS = (INTL, MOBILE, LANDLINE)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}")

# 연락 수단이 적힌 문장은 통째로 걷어낸다.
# "카톡 아이디 abc123 으로 주세요" 처럼 형식이 제각각이라 부분 치환으로는 못 잡는다
CONTACT = re.compile(r"[^.!?]*(카톡|카카오|인스타|디엠|DM|문자\s?주|연락\s?주)[^.!?]*[.!?]?")


def build_address_pattern(gu_names, dong_names=()):
    """자치구·행정동 목록으로 주소 정규식을 만든다. 목록이 비면 None.

    이 파일은 DB를 모르므로 목록을 밖에서 받는다 (mask 의 names 와 같은 방식).
    """
    words = set()

    for gu in gu_names:
        if not gu:
            continue
        words.add(gu)                                  # '강남구'
        short = gu[:-1] if gu.endswith("구") else gu    # '강남'
        # '중구' -> '중' 은 버린다. 실측 921회가 전부 집중·중요·도중 같은 오탐이었다
        if len(short) >= 2:
            words.add(short)

    words.update(d for d in dong_names if d)           # '역삼1동'

    if not words:
        return None

    # 긴 것부터 — '강남'이 앞에 오면 '강남구'의 '구'가 남는다 (이름 지울 때와 같은 이유)
    ordered = sorted(words, key=len, reverse=True)
    joined = "|".join(re.escape(w) for w in ordered)

    # 뒤에 붙는 '역삼동' 같은 조각도 같이 먹는다
    return re.compile(rf"(?:{joined})(?:\s?[가-힣]+동)?")


def _tidy(text: str) -> str:
    """가리고 나면 생기는 연속 공백을 정리한다."""
    return re.sub(r"\s{2,}", " ", text).strip()


def mask(text: str, *, names=(), address=None) -> str:
    """개인정보를 지운다. 되돌릴 수 없으므로 '나가는 글'에만 쓴다."""
    if not text:
        return text

    text = CONTACT.sub(" ", text)

    # 국제 표기를 먼저 — MOBILE 이 먼저 잡으면 '+82-' 가 남는다
    for pattern in PHONE_PATTERNS:
        text = pattern.sub("[연락처]", text)

    text = EMAIL.sub("[메일]", text)
    if address is not None:
        text = address.sub("[주소]", text)

    # 긴 이름부터 지운다 — "김민"이 "김민수"보다 먼저 지워지면 "수"가 남는다
    for name in sorted({n for n in names if n and len(n) >= 2}, key=len, reverse=True):
        if name in text:
            text = text.replace(name, "[이름]")

    return _tidy(text)




