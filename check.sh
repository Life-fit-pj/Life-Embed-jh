#!/usr/bin/env bash
# 계층이 지켜지나 세 가지를 센다. 저장소 뿌리에서  bash check.sh

echo
echo "① 창구·엔진에 SQL이 있으면 안 된다"
if grep -rnE "SELECT |INSERT |UPDATE |DELETE FROM|CREATE TABLE" --include=*.py app/features app/engine; then
    echo "  X 위에 나온 곳들을 app/tables/ 로 내려야 한다"
else
    echo "  OK 0곳"
fi

echo
echo "② 함수 안 import 가 있으면 안 된다"
if grep -rn "^ \+from app\." --include=*.py app/; then
    echo "  X 맨 위로 올린다. 올려서 죽으면 진짜 순환이다"
else
    echo "  OK 0곳"
fi

echo
echo "③ 계층 방향"
python -m pytest tests/test_layers.py -q
