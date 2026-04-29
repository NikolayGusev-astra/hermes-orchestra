#!/usr/bin/env bash
# Hermes-Orchestra — one-command installer
# Usage: curl -fsSL https://raw.githubusercontent.com/NikolayGusev-astra/hermes-orchestra/main/install.sh | bash
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[+]${NC} $1"; }
ok()    { echo -e "${GREEN}[✓]${NC} $1"; }
err()   { echo -e "${RED}[✗]${NC} $1"; exit 1; }

REPO_URL="https://github.com/NikolayGusev-astra/hermes-orchestra.git"
INSTALL_DIR="${HERMES_ORCHESTRA_HOME:-$HOME/.hermes-orchestra}"
HERMES_BIN="${HERMES_BIN:-$HOME/.local/bin/hermes}"

# ---- Step 1: Check / Install Hermes ----
info "Проверяю Hermes Agent..."
if command -v hermes &>/dev/null; then
    ok "Hermes уже установлен: $(hermes --version 2>/dev/null || echo $(which hermes))"
    HERMES_BIN="$(which hermes)"
elif [ -f "$HERMES_BIN" ]; then
    ok "Hermes найден: $HERMES_BIN"
else
    info "Hermes не найден. Устанавливаю..."
    curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
    if ! command -v hermes &>/dev/null; then
        err "Hermes не установился. Установите вручную: curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash"
    fi
    ok "Hermes установлен"
fi

# ---- Step 2: Clone extension ----
info "Клонирую Hermes-Orchestra..."
if [ -d "$INSTALL_DIR" ]; then
    info "Репозиторий уже есть, обновляю..."
    git -C "$INSTALL_DIR" pull --ff-only 2>/dev/null || true
else
    git clone "$REPO_URL" "$INSTALL_DIR"
fi
ok "Репозиторий: $INSTALL_DIR"

# ---- Step 3: Find Hermes tools directory ----
# Hermes может быть установлен в ~/.hermes/hermes-agent/ или в /usr/lib/hermes-agent/
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
TOOLS_DIR_SRC="$INSTALL_DIR/tools"

# Ищем куда класть тулы
CANDIDATES=(
    "$HOME/.local/share/hermes/hermes-agent/tools"
    "$HOME/.hermes/hermes-agent/tools"
    "/usr/local/share/hermes/hermes-agent/tools"
    "/usr/share/hermes/hermes-agent/tools"
    "$(dirname $(which hermes 2>/dev/null))/../tools"
)

HERMES_TOOLS_DIR=""
for dir in "${CANDIDATES[@]}"; do
    expanded=$(eval echo "$dir")
    if [ -d "$expanded" ]; then
        HERMES_TOOLS_DIR="$expanded"
        break
    fi
done

# Fallback: создать в ~/.hermes/hermes-agent/tools/
if [ -z "$HERMES_TOOLS_DIR" ]; then
    info "Не удалось определить tools directory. Создаю $HERMES_HOME/hermes-agent/tools/"
    mkdir -p "$HERMES_HOME/hermes-agent/tools"
    HERMES_TOOLS_DIR="$HERMES_HOME/hermes-agent/tools"
fi

# ---- Step 4: Install tools ----
info "Устанавливаю tools в $HERMES_TOOLS_DIR..."
for f in "$TOOLS_DIR_SRC"/*.py; do
    basename=$(basename "$f")
    cp "$f" "$HERMES_TOOLS_DIR/$basename"
    ok "  $basename"
done

# ---- Step 5: Install skill ----
SKILL_DIR="$HERMES_HOME/skills"
mkdir -p "$SKILL_DIR"
if [ -f "$INSTALL_DIR/SKILL.md" ]; then
    cp "$INSTALL_DIR/SKILL.md" "$SKILL_DIR/hermes-orchestra.md"
    ok "Skill установлен: $SKILL_DIR/hermes-orchestra.md"
fi

# ---- Step 6: Register toolset if hermes config exists ----
if command -v hermes &>/dev/null; then
    info "Проверяю, что toolset 'orchestra' активен..."
    hermes tools enable orchestra 2>/dev/null || true
fi

# ---- Done ----
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Hermes-Orchestra установлен!          ║${NC}"
echo -e "${GREEN}╠════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  Команды:                                  ║${NC}"
echo -e "${GREEN}║  hermes -s hermes-orchestra               ║${NC}"
echo -e "${GREEN}║  > project_create(name=\"Мой проект\")     ║${NC}"
echo -e "${GREEN}║  > task_create(project_id=\"...\", ...)    ║${NC}"
echo -e "${GREEN}║  > task_breakdown(parent_task_id=\"...\", ║${NC}"
echo -e "${GREEN}║      subtasks=[{title:\"А\"},{title:\"Б\"}])║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""
info "Чтобы использовать:"
echo "  hermes -s hermes-orchestra"
echo "  # Или в сессии: /skill hermes-orchestra"
