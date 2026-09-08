"""옛 SQL 구현과 새 ORM 구현이 같은 결과를 내는지 대조한다.

실제 life.db 는 건드리지 않는다. 사본 두 개를 만들어
  old.db ← 옛 구현 / new.db ← 새 구현
을 각각 돌린 뒤, 반환값과 표 내용을 둘 다 비교한다.

옛 구현은 git 에서 꺼내 tools/_old_history.py 로 둔다(B2-8절 ①).

실행: py tools/compare_history.py
"""

import importlib.util
import os
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OLD_SRC = ROOT / "tools" / "_old_history.py"
OLD_DB = ROOT / "old.db"
NEW_DB = ROOT / "new.db"

shutil.copy(ROOT / "data" / "life.db", OLD_DB)
shutil.copy(ROOT / "data" / "life.db", NEW_DB)

# 새 구현(ORM)은 DATABASE_URL 을 읽는다 -> 사본 new.db
# ★ import 보다 먼저 넣어야 한다. app/core/config.py 는 불러올 때 한 번만 읽는다
os.environ["DATABASE_URL"] = f"sqlite:///{NEW_DB.as_posix()}"
sys.path.insert(0, str(ROOT))

# 옛 구현은 app.core.db 의 DB_PATH 를 쓴다 -> 사본 old.db 로 갈아 끼운다
import app.core.db as core_db

core_db.DB_PATH = OLD_DB


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


old = load("old_history", OLD_SRC)
from app.tables import history as new

ID = "test-anon"

# (설명, 부를 것, 표를 확인할 SQL)
STEPS = [
    ("add_like",             lambda m: m.add_like(ID, "강남구", "역삼1동"),
     "SELECT anon_id, 구, 행정동명 FROM likes ORDER BY 1,2,3"),
    ("add_like 두 번(무시)",  lambda m: m.add_like(ID, "강남구", "역삼1동"),
     "SELECT COUNT(*) FROM likes"),
    ("list_likes",           lambda m: m.list_likes(ID), "SELECT COUNT(*) FROM likes"),
    ("like_count",           lambda m: m.like_count("강남구", "역삼1동"), "SELECT COUNT(*) FROM likes"),
    ("like_region_counts",   lambda m: m.like_region_counts(), "SELECT COUNT(*) FROM likes"),
    ("remove_like",          lambda m: m.remove_like(ID, "강남구", "역삼1동"),
     "SELECT COUNT(*) FROM likes"),

    ("add_search_history",   lambda m: m.add_search_history(ID, "조용한 동네"),
     "SELECT anon_id, query FROM search_history ORDER BY 1,2"),
    ("list_search_history",  lambda m: m.list_search_history(ID), "SELECT COUNT(*) FROM search_history"),
    ("top_searches",         lambda m: m.top_searches(), "SELECT COUNT(*) FROM search_history"),
    ("search_count",         lambda m: m.search_count(), "SELECT COUNT(*) FROM search_history"),

    ("add_chat_history",     lambda m: m.add_chat_history(ID, "질문", "답"),
     "SELECT anon_id, question, answer FROM chat_history"),
    ("list_chat_history",    lambda m: m.list_chat_history(ID), "SELECT COUNT(*) FROM chat_history"),
    ("chat_count",           lambda m: m.chat_count(), "SELECT COUNT(*) FROM chat_history"),

    ("write_admin_log",      lambda m: m.write_admin_log("member", "C001", {"녹지": 5}),
     "SELECT target, target_id, patch FROM admin_log"),
    ("admin_log_count",      lambda m: m.admin_log_count(), "SELECT COUNT(*) FROM admin_log"),
    ("admin_log_recent",     lambda m: m.admin_log_recent(), "SELECT COUNT(*) FROM admin_log"),

    ("add_analysis_chat",    lambda m: m.add_analysis_chat("질문", "답" * 60, "{}", "2026-01-01"),
     "SELECT chat_id, question, created_at FROM analysis_chat"),
    ("list_analysis_chat",   lambda m: m.list_analysis_chat(), "SELECT COUNT(*) FROM analysis_chat"),
    ("analysis_chat_one",    lambda m: m.analysis_chat_one(1), "SELECT COUNT(*) FROM analysis_chat"),
    ("delete_analysis_chat", lambda m: m.delete_analysis_chat(1), "SELECT COUNT(*) FROM analysis_chat"),
]


def read(path, sql):
    con = sqlite3.connect(path)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


ok = bad = 0
for label, call, check in STEPS:
    before, after = call(old), call(new)
    rows_before, rows_after = read(OLD_DB, check), read(NEW_DB, check)

    if before == after and rows_before == rows_after:
        print(f"[같음] {label:<24} 반환 {before!r}")
        ok += 1
    else:
        print(f"[다름] {label}")
        print(f"       반환  옛 {before!r}  /  새 {after!r}")
        print(f"       표    옛 {rows_before}")
        print(f"             새 {rows_after}")
        bad += 1

print(f"\n같음 {ok} · 다름 {bad} · 전체 {len(STEPS)}")

from app.db import engine

engine.dispose()
core_db.get_con().close()
OLD_DB.unlink(missing_ok=True)
NEW_DB.unlink(missing_ok=True)
print("사본 삭제 완료 — 실제 life.db 는 안 건드렸다")
