#!/data/data/com.termux/files/usr/bin/bash

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
CYAN='\033[1;36m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
RED='\033[1;31m'
BOLD='\033[1m'
RESET='\033[0m'

clear
echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                    SVA MATRIX SQUAD                      ║"
echo "║                  INSTALLATION SYSTEM                     ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${RESET}"

if command -v pkg >/dev/null 2>&1; then
    echo -e "${GREEN}📱 Termux detected${RESET}"
    echo -e "${YELLOW}📦 Installing Python...${RESET}"
    pkg update -y
    pkg install -y python
else
    echo -e "${GREEN}🐧 Linux detected${RESET}"
    echo -e "${YELLOW}📦 Installing Python...${RESET}"

    if command -v apt-get >/dev/null 2>&1; then
        if [ "$(id -u)" -eq 0 ]; then
            apt-get update
            apt-get install -y python3 python3-pip
        elif command -v sudo >/dev/null 2>&1; then
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip
        else
            echo -e "${RED}❌ sudo is required to install Python.${RESET}"
            exit 1
        fi
    else
        echo -e "${RED}❌ apt-get not found.${RESET}"
        exit 1
    fi
fi

echo
echo -e "${YELLOW}${BOLD}📦 Installing Python dependencies...${RESET}"
python3 -m pip install -r "$PROJECT_DIR/requirements.txt"

chmod +x "$PROJECT_DIR/SVA-Matrix.py"

if command -v pkg >/dev/null 2>&1; then
    LAUNCHER="$PREFIX/bin/sva"
    cat > "$LAUNCHER" <<LAUNCHER_EOF
#!/data/data/com.termux/files/usr/bin/bash
exec python3 "$PROJECT_DIR/SVA-Matrix.py" "\$@"
LAUNCHER_EOF
else
    LAUNCHER="$HOME/.local/bin/sva"
    mkdir -p "$HOME/.local/bin"
    cat > "$LAUNCHER" <<LAUNCHER_EOF
#!/usr/bin/env bash
exec python3 "$PROJECT_DIR/SVA-Matrix.py" "\$@"
LAUNCHER_EOF
fi

chmod +x "$LAUNCHER"

echo
echo -e "${GREEN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║              ✅ INSTALLATION COMPLETE                    ║"
echo "║                                                          ║"
echo "║              🚀 SVA MATRIX READY                        ║"
echo "║                                                          ║"
echo "║              Run:  sva                                   ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${RESET}"
