import json
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.history import AdminLog, AnalysisChat, ChatHistory, Like, SearchHistory, UserLogin


def create_login(db, customer_id, login_id, password):
    """login_id 자리를 선점한다. 이미 있으면 아무것도 안 하고 False.

    login_id 가 기본키라 on_conflict_do_nothing() 이 "동시에 둘이 와도 하나만
    성공"을 DB 단에서 보장한다 — 회원가입이 겹쳐 들어올 때(중복 클릭 등)
    customer 행이 여러 개 생기는 걸 여기서 막는다(signup() 참고).
    """
    result = db.execute(
        pg_insert(UserLogin)
        .values(customer_id=customer_id, login_id=login_id, password=password)
        .on_conflict_do_nothing()
    )
    db.commit()
    return result.rowcount > 0


def update_login_customer(db, login_id, customer_id):
    """선점해 둔 login_id 자리에 실제 customer_id 를 채운다(signup() 2단계)."""
    db.query(UserLogin).filter(UserLogin.login_id == login_id).update({"customer_id": customer_id})
    db.commit()


def delete_login(db, login_id):
    """선점만 하고 customer 생성에 실패했을 때 자리를 반납한다(signup() 실패 복구)."""
    db.query(UserLogin).filter(UserLogin.login_id == login_id).delete(synchronize_session=False)
    db.commit()


def delete_logins_by_customer(db, customer_id):
    """회원 탈퇴 시 이 customer_id 에 붙은 로그인 계정을 전부 지운다.

    customer_id 는 유일하지 않다(계정 풀 소진 시 여러 login_id 가 붙을 수 있다) —
    login_id 하나만 지우는 delete_login() 과 다르다.
    """
    db.query(UserLogin).filter(UserLogin.customer_id == customer_id).delete(synchronize_session=False)
    db.commit()


def delete_activity(db, anon_id):
    """회원 탈퇴 시 이 사람이 남긴 좋아요·검색·채팅 기록을 지운다.

    로그인한 회원은 anon_id 자리가 customer_id 로 덮어써져 있다(admin_service.get_member 참고).
    """
    db.query(Like).filter(Like.anon_id == anon_id).delete(synchronize_session=False)
    db.query(SearchHistory).filter(SearchHistory.anon_id == anon_id).delete(synchronize_session=False)
    db.query(ChatHistory).filter(ChatHistory.anon_id == anon_id).delete(synchronize_session=False)
    db.commit()


def get_login_row(db, login_id):
    row = db.query(UserLogin.customer_id, UserLogin.password).filter(UserLogin.login_id == login_id).first()
    return {"customer_id": row[0], "password": row[1]} if row else None


def login_customer_ids(db):
    return [cid for (cid,) in db.query(UserLogin.customer_id).all()]


def add_like(db, anon_id, gu, dong):
    """좋아요 추가. 이미 있으면 아무 일도 안 한다.

    db.add(Like(...)) 를 쓰면 이미 있을 때 IntegrityError 로 죽는다.
    옛 SQL 의 INSERT OR IGNORE 를 그대로 재현하려면 on_conflict_do_nothing 이 필요하다.

    on_conflict_do_nothing() 은 방언 전용이라 sqlalchemy.dialects.postgresql 의
    insert 를 쓴다. 이게 Postgres 에서 동작하려면 진짜 제약이 있어야 하는데,
    likes 의 기본키 (anon_id, 구, 행정동명) 이 그것이다 — 모델에 셋 다
    primary_key=True 로 적혀 있어서 create_all() 이 진짜 PK 로 만들어 준다
    (app/models/history.py)
    """
    db.execute(
        pg_insert(Like)
        .values(anon_id=anon_id, 구=gu, 행정동명=dong)
        .on_conflict_do_nothing()
    )
    db.commit()


def remove_like(db, anon_id, gu, dong):
    """좋아요 취소."""
    db.query(Like).filter(
        Like.anon_id == anon_id,
        Like.구 == gu,
        Like.행정동명 == dong,
    ).delete(synchronize_session=False)
    db.commit()


def add_search_history(db, anon_id, query):
    """검색어 기록 추가. 같은 검색어라도 매번 새 줄로 남긴다.

    created_at 을 안 넣는다 — 모델의 server_default 가 DB 에게 맡긴다(3B-4절).
    """
    db.add(SearchHistory(anon_id=anon_id, query=query))
    db.commit()


def list_search_history(db, anon_id, limit=20):
    """최근 검색어부터 반환."""
    fields = ("query", "created_at")

    return [
        dict(zip(fields, row))
        for row in db.query(SearchHistory.query, SearchHistory.created_at)
        .filter(SearchHistory.anon_id == anon_id)
        .order_by(SearchHistory.created_at.desc())
        .limit(limit)
        .all()
    ]


def add_analysis_chat(db, question, answer, facts_json, created_at):
    """대화 한 건을 남기고 새 chat_id 를 돌려준다.

    옛 코드는 커서의 lastrowid 를 읽었다. ORM 은 commit 뒤에 객체의
    chat_id 를 그냥 읽으면 된다 — DB 가 매긴 번호를 SQLAlchemy 가 채워 준다.

    ★ 반드시 세션이 살아 있을 때 읽는다. 다리(_run)가 함수를 나가면서
      세션을 닫으므로, return 문 안에서 읽는 지금 모양이어야 한다
    """
    chat = AnalysisChat(
        question=question,
        answer=answer,
        facts=facts_json,
        created_at=created_at,
    )
    db.add(chat)
    db.commit()
    return chat.chat_id


def delete_analysis_chat(db, chat_id):
    """대화 하나를 지운다. 지운 줄 수를 돌려준다.

    query(...).delete() 가 지운 줄 수를 그대로 돌려준다 — rowcount 를 꺼낼 일이 없다.
    """
    deleted = (
        db.query(AnalysisChat)
        .filter(AnalysisChat.chat_id == chat_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


def like_region_counts(db, limit=15):
    """좋아요가 많이 눌린 동네. (동네이름, 개수) 목록."""
    name = Like.구 + " " + Like.행정동명       # 글자 칸이라 || 로 번역된다
    total = func.count()

    return [
        tuple(row)
        for row in db.query(name, total)
        .group_by(name)
        .order_by(total.desc())
        .limit(limit)
        .all()
    ]


def list_analysis_chat(db, limit=50):
    """대화 목록. 답은 90자까지만 미리보기로 싣는다."""
    fields = ("chat_id", "question", "preview", "created_at")
    preview = func.substr(AnalysisChat.answer, 1, 90)

    return [
        dict(zip(fields, row))
        for row in db.query(
            AnalysisChat.chat_id, AnalysisChat.question, preview, AnalysisChat.created_at
        )
        .order_by(AnalysisChat.chat_id.desc())
        .limit(limit)
        .all()
    ]


def list_likes(db, anon_id):
    """이 사람이 좋아요 누른 동네 목록. 최근 순."""
    fields = ("구", "행정동명", "created_at")

    return [
        dict(zip(fields, row))
        for row in db.query(Like.구, Like.행정동명, Like.created_at)
        .filter(Like.anon_id == anon_id)
        .order_by(Like.created_at.desc())
        .all()
    ]


def add_chat_history(db, anon_id, question, answer):
    """채팅 질문/답변 기록 추가.

    created_at 을 안 넣는다 — 모델의 server_default 가 DB 에게 맡긴다.
    """
    db.add(ChatHistory(anon_id=anon_id, question=question, answer=answer))
    db.commit()


def list_chat_history(db, anon_id, limit=20):
    """최근 대화부터 반환."""
    fields = ("question", "answer", "created_at")

    return [
        dict(zip(fields, row))
        for row in db.query(ChatHistory.question, ChatHistory.answer, ChatHistory.created_at)
        .filter(ChatHistory.anon_id == anon_id)
        .order_by(ChatHistory.created_at.desc())
        .limit(limit)
        .all()
    ]


def write_admin_log(db, target, target_id, patch):
    """수정 한 건을 남긴다.

    json.dumps 와 datetime.now() 는 옛 함수가 하던 그대로 여기에 둔다.
    admin_log 는 DDL 에 DEFAULT 가 없어서 시각을 파이썬이 만들어 넣어야 한다
    """
    db.add(AdminLog(
        target=target,
        target_id=target_id,
        patch=json.dumps(patch, ensure_ascii=False),
        changed_at=datetime.now().isoformat(timespec="seconds"),
    ))
    db.commit()


def admin_log_recent(db, limit=8):
    """관리자 수정 이력 최근 몇 건."""
    fields = ("target", "target_id", "patch", "changed_at")

    return [
        dict(zip(fields, row))
        for row in db.query(
            AdminLog.target, AdminLog.target_id, AdminLog.patch, AdminLog.changed_at
        )
        .order_by(AdminLog.log_id.desc())
        .limit(limit)
        .all()
    ]


def like_count(db, gu, dong):
    """이 동네에 좋아요가 몇 개 눌렸나."""
    return (
        db.query(func.count())
        .select_from(Like)
        .filter(Like.구 == gu, Like.행정동명 == dong)
        .scalar()
    )


def search_count(db):
    """검색이 몇 건 쌓였나."""
    return db.query(func.count()).select_from(SearchHistory).scalar()


def chat_count(db):
    """대화가 몇 건 쌓였나."""
    return db.query(func.count()).select_from(ChatHistory).scalar()


def admin_log_count(db):
    """관리자가 몇 번 고쳤나."""
    return db.query(func.count()).select_from(AdminLog).scalar()


def top_searches(db, top=20):
    """많이 찾은 검색어. (검색어, 횟수) 목록."""
    total = func.count()

    return [
        tuple(row)
        for row in db.query(SearchHistory.query, total)
        .group_by(SearchHistory.query)
        .order_by(total.desc())
        .limit(top)
        .all()
    ]


def analysis_chat_one(db, chat_id):
    """대화 하나를 통째로. 없으면 None."""
    row = db.query(AnalysisChat).filter(AnalysisChat.chat_id == chat_id).first()
    if row is None:
        return None

    return {
        "chat_id": row.chat_id,
        "question": row.question,
        "answer": row.answer,
        "facts": row.facts,
        "created_at": row.created_at,
    }
