#!/usr/bin/env sh
# Links the FastAPI skill bundled in the installed package into Claude Code.
# Run again after changing the Python version or recreating .venv.
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"

skill=$(uv run python -c "import pathlib, fastapi; print(pathlib.Path(fastapi.__file__).parent / '.agents/skills/fastapi')")

if [ ! -f "$skill/SKILL.md" ]; then
  echo "FastAPI skill not found at $skill" >&2
  exit 1
fi

mkdir -p .claude/skills
ln -sfn "$skill" .claude/skills/fastapi
echo "Linked .claude/skills/fastapi -> $skill"
