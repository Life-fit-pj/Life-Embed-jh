"""DB의 회원 이름과 마스킹 규칙을 연결한다. 앱은 이 파일의 mask_text 만 부른다."""

from app.domain import masking
from app.tables.members import customer_names
from app.tables.regions import dong_names, gu_names

_names = None
_address = None


def _load() -> None:
    global _names, _address
    if _names is not None:
        return
    _names = customer_names()
    _address = masking.build_address_pattern(gu_names(), dong_names())



def reset() -> None:
    global _names, _address
    _names = None
    _address = None


def mask_text(text: str) -> str:
    _load()
    return masking.mask(text, names=_names, address=_address)

