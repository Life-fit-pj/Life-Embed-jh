"""계층이 한 방향으로만 흐르나. import 그래프를 떠서 본다."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# 번호가 작을수록 아래층. 아래층은 위층을 부르면 안 된다.
LAYER = {
    "app.domain": 0,
    "app.schemas": 1,      # 9단계 — 형식만 적은 것. 아무것도 안 부른다
    "app.core": 1,
    "app.db": 1,           # Base · engine · SessionLocal. core 만 부른다
    "app.models": 2,       # 표를 클래스로. db 만 부른다
    "app.repositories": 2,
    "app.ai": 2,
    "app.rag": 3,          # 7단계 — ai 위, engine 아래
    "app.engine": 4,
    "app.services": 5,     # 8단계 — 업무 로직
    "app.tools": 5,        # 채팅 도구. services(recommend_by_weights)를 부른다
    "app.graph": 5,        # services 와 서로 부른다 — 순환이다(check.sh ②)
    "app.api": 7,          # 9단계 — 맨 위. 여기만 FastAPI 를 안다
    "app.main": 8,         # 라우터를 거는 곳. api 만 부른다
}

# 4단계에서 chunker 가 app/ai/ 로 올라와 예외가 사라졌다.
# 다시 채워야 할 일이 생기면 그건 층을 거스른다는 뜻이다
ALLOWED_PIPELINE = set()


# 파일 경로를 app.core.db 같은 모듈 이름으로 바꾼다
def module_name(path):
    rel = path.relative_to(ROOT).with_suffix("")
    return ".".join(rel.parts).removesuffix(".__init__")


# 그 모듈이 몇 층인가. 못 찾으면 (None, None)
def layer_of(module):
    for prefix in sorted(LAYER, key=len, reverse=True):
        if module == prefix or module.startswith(prefix + "."):
            return LAYER[prefix], prefix
    return None, None


# app/ 안의 (부르는 쪽, 불리는 쪽) 전부
def edges():
    out = []
    for path in sorted((ROOT / "app").rglob("*.py")):
        source = module_name(path)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module and node.module.startswith(("app", "pipeline")):
                    out.append((source, node.module))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(("app", "pipeline")):
                        out.append((source, alias.name))
    return out


# (부르는 쪽, 불리는 쪽) 중 아래층이 위층을 부르는 것만 고른다
def broken(pairs):
    out = []
    for source, target in pairs:
        up, source_layer = layer_of(source)
        down, target_layer = layer_of(target)
        if up is None or down is None or source_layer == target_layer:
            continue
        if down > up:
            out.append(f"{source} -> {target}  ({source_layer} -> {target_layer})")
    return out


def test_아래층이_위층을_안_부른다():
    found = broken(edges())
    assert not found, "아래층이 위층을 가리킨다:\n  " + "\n  ".join(found)


def test_모든_모듈이_표에_있다():
    missing = sorted(m for m in (module_name(p) for p in (ROOT / "app").rglob("*.py"))
                     if layer_of(m)[0] is None)
    assert not missing, "LAYER 에 없는 모듈은 검사가 건너뛴다:\n  " + "\n  ".join(missing)


def test_검사기가_위반을_잡는다():
    assert broken([("app.core.config", "app.services.search_service")])
    assert not broken([("app.services.search_service", "app.core.config")])

def test_domain_은_아무것도_안_부른다():
    outward = [f"{s} -> {t}" for s, t in edges()
               if s.startswith("app.domain") and not t.startswith("app.domain")]
    assert not outward, "domain 이 밖을 본다:\n  " + "\n  ".join(outward)


def test_app_이_pipeline_을_부르는_곳은_허락된_한_줄뿐():
    found = {(s, t) for s, t in edges() if t.startswith("pipeline")}
    assert found <= ALLOWED_PIPELINE, (
        "app 이 pipeline 을 새로 부른다:\n  "
        + "\n  ".join(f"{s} -> {t}" for s, t in sorted(found - ALLOWED_PIPELINE))
    )
