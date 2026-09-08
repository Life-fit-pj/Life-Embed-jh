"""Life-Web 이 엔진에서 가져가는 이름이 전부 살아 있나.

Life-Web/services/engine.py 20~36행이 계약이다.
하나라도 없으면 웹이 화면을 그리기 전에 import 단계에서 죽는다.
파일을 옮기는 작업(8단계) 중에는 한 파일 옮길 때마다 돌린다.

실행: py -m tools.check_contract      (저장소 뿌리에서)

★ 반드시 -m 으로 부른다. 파일 경로로 실행하면(py tools/check_contract.py)
  검색 경로 맨 앞이 tools/ 가 되어 저장소 뿌리가 안 잡힌다. 그러면 계약 39개가
  전부 "import 자체가 실패" 로 나오는데, 코드는 멀쩡하고 부르는 법만 틀린 것이다
"""

import importlib

CONTRACT = {
    "app.tables.history": ["add_like", "remove_like", "add_search_history",
                           "list_search_history", "add_chat_history", "list_chat_history"],
    "app.tables.regions": ["facilities", "facility_counts", "region_extras"],
    "app.tables.members": ["customer_one"],
    "app.features.search": ["search", "recommend_by_weights",
                            "recommend_by_weights_explained"],
    "app.features.region_explain": ["region_explain_cached"],
    "app.features.chat": ["chat"],
    "app.features.survey": ["score_survey"],
    "app.features.analysis": ["ask", "list_chats", "get_chat", "delete_chat"],
    "app.features.admin": ["get_member", "list_members", "get_region", "list_regions",
                           "update_member", "update_region", "preview_member",
                           "similar_members", "InvalidPatch", "health", "clear_caches",
                           "privacy_preview", "dashboard", "recent_logs", "create_member"],
    "app.features.auth": ["login_with_supabase", "backfill_logins", "signed_up", "signup"],
}


def main():
    missing = []

    for module_name, names in CONTRACT.items():
        try:
            module = importlib.import_module(module_name)
        except Exception as error:
            missing.append(f"{module_name}  (import 자체가 실패: {error})")
            continue

        missing += [f"{module_name}.{n}" for n in names if not hasattr(module, n)]

    total = sum(len(names) for names in CONTRACT.values())

    if missing:
        print(f"빠진 것 {len(missing)} / {total}")
        for item in missing:
            print("  -", item)
    else:
        print(f"계약 {total}개 전부 살아 있다")


if __name__ == "__main__":
    main()
