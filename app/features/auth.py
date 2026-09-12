"""옛 이름을 지키는 다리. 실제 내용은 app/services/auth_service.py 에 있다.

Life-Web/services/engine.py 가 app.features.* 를 이름으로 직접 import 한다(8-0절).
리팩토링 후 필요없어지면 팀원이 이 다리 여덟 개를 한꺼번에 지운다.
"""

from app.services.auth_service import *      # noqa: F401,F403
