import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

"""계층이 한 방향으로만 흐르나. import 그래프를 떠서 본다."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 번호가 작을수록 아래층. 아래층은 위층을 부르면 안 된다.
# app.adapters 와 app.llm 이 둘 다 있는 건 2단계 전/후 모두에서 돌게 하려는 것이다
LAYER = {
    "app.domain": 0,
    "app.core": 1,
    "app.tables": 2,
    "app.adapters": 2,
    "app.llm": 2,
    "app.engine": 3,
    "app.features": 4,
}

# app 이 pipeline 을 부르는 건 이 한 줄만 허락한다 (청킹 규칙을 두 벌 두지 않으려고)
ALLOWED_PIPELINE = {("app.engine.resync", "pipeline.prep.chunking")}


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
