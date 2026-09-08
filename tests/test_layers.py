import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

"""계층이 한 방향으로만 흐르나. import 그래프를 떠서 본다."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 번호가 작을수록 아래층. 아래층은 위층을 부르면 안 된다.
LAYER = {
    "app.domain": 0,
    "app.schemas": 1,      # 9단계 — 형식만 적은 것. 아무것도 안 부른다
    "app.core": 1,
    "app.tables": 2,
    "app.repositories": 2,
    "app.ai": 2,
    "app.rag": 3,          # 7단계 — ai 위, engine 아래
    "app.engine": 4,
    "app.services": 5,     # 8단계 — 업무 로직
    "app.features": 6,     # 다리만 남았다. 팀원이 웹을 합칠 때 지운다
    "app.api": 7,          # 9단계 — 맨 위. 여기만 FastAPI 를 안다
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


def test_아래층이_위층을_안_부른다():
    broken = []
    for source, target in edges():
        up, source_layer = layer_of(source)
        down, target_layer = layer_of(target)
        if up is None or down is None or source_layer == target_layer:
            continue
        if down > up:
            broken.append(f"{source} -> {target}  ({source_layer} -> {target_layer})")
    assert not broken, "아래층이 위층을 가리킨다:\n  " + "\n  ".join(broken)


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

def test_api_는_다리를_안_부른다():
    """app/features/ 는 Life-Web 을 위한 다리다. 팀원이 웹을 합칠 때 통째로 지운다.

    새로 만드는 app/api/ 가 거기 기대면 그때 같이 깨진다.
    api 는 app/services/ 를 곧장 부른다
    """
    leaning = [f"{s} -> {t}" for s, t in edges()
               if s.startswith("app.api") and t.startswith("app.features")]

    assert not leaning, "api 가 다리에 기댄다:\n  " + "\n  ".join(leaning)


