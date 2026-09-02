"""DB의 회원 이름과 마스킹 규칙을 연결한다. 앱은 이 파일의 mask_text 만 부른다."""

from app.core.db import dicts
from app.domain import masking

_names = None
_address = None


def _load() -> None:
    global _names, _address
    if _names is not None:
        return
    _names = [r["name"] for r in dicts("SELECT name FROM customers") if r["name"]]
    _address = masking.build_address_pattern(
        [r["구"] for r in dicts("SELECT DISTINCT 구 FROM master_dataset_v3")],
        [r["행정동명"] for r in dicts("SELECT DISTINCT 행정동명 FROM master_dataset_v3")],
    )


def reset() -> None:
    global _names, _address
    _names = None
    _address = None


def mask_text(text: str) -> str:
    _load()
    return masking.mask(text, names=_names, address=_address)

