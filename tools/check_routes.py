# tools/check_routes.py
"""Life-Web 이 부르는 HTTP 경로가 엔진에 다 열렸나.

check_contract.py 가 파이썬 이름을 세던 자리다. Life-Web 이 HTTP 로 넘어간 뒤
진짜 계약은 경로이므로 이쪽이 맞다. 실행: py -m tools.check_routes
"""

import io
import re

from app.main import app

WEB = "../Life-Web/services/engine.py"


def _shape(path):
    """{gu}/{dong} 과 {quote(gu)}/{quote(dong)} 을 같은 모양으로 만든다."""
    return re.sub(r"\{[^}]*\}", "{}", path)


def main():
    opened = {
        (method.upper(), _shape(path))
        for path, ops in app.openapi()["paths"].items()
        for method in ops
    }

    web = io.open(WEB, encoding="utf-8").read()
    called = {
        (method, _shape(path))
        for method, path in re.findall(
            r'_call\(\s*"(GET|POST|PATCH|DELETE)",\s*f?"([^"]+)"', web
        )
    }
    called.add(("POST", "/admin/analysis/ask"))   # _AnalysisEngine 이 _client 로 직접 친다

    missing = sorted(called - opened)
    print(f"엔진이 여는 경로 {len(opened)} · 웹이 부르는 것 {len(called)}")
    print("못 여는 것:", missing if missing else "없음")


if __name__ == "__main__":
    main()
