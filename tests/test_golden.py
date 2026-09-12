"""사진과 지금을 비교한다. 리팩터링 단계마다 돌린다.

실행: py -m pytest tests/test_golden.py -v
"""

import json

import pytest

from tests.make_golden import GOLDEN, SNAPS


def load(name):
    path = GOLDEN / f"{name}.json"
    if not path.exists():
        pytest.skip(f"{name}.json 이 없다. 먼저 py -m tests.make_golden 을 돌린다")
    return json.loads(path.read_text(encoding="utf-8"))


# 사진 이름을 하나씩 넣어 같은 검사를 네 번 돌린다.
# 함수를 따로 쓰면 사진이 늘 때마다 함수도 늘어난다.
@pytest.mark.parametrize("name", sorted(SNAPS))
def test_옮기기_전과_같다(name):
    expected = load(name)
    actual = json.loads(json.dumps(SNAPS[name](), ensure_ascii=False))

    assert actual == expected, (
        f"{name} 이 달라졌다.\n"
        f"  전: {expected}\n"
        f"  후: {actual}"
    )
