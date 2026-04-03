#!/bin/bash
# Turtle Bot Web Dashboard Launcher

cd "$(dirname "$0")"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${PURPLE}                    TURTLE BOT WEB DASHBOARD                              ${NC}"
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check that web/app.py exists
if [ ! -f "web/app.py" ]; then
    echo -e "${YELLOW}WARNING: web/app.py not found. The web dashboard directory is not included${NC}"
    echo -e "${YELLOW}in this repository. Add your web/app.py to use this launcher.${NC}"
    echo ""
    exit 1
fi

echo -e "${CYAN}Starting web dashboard...${NC}"
echo -e "${CYAN}Dashboard will open at: ${GREEN}http://localhost:5001${NC}"
echo ""

# Wait a moment for the message to display
sleep 1

# Open browser after a short delay (try common browsers, fall back to xdg-open)
(sleep 3 && \
    google-chrome --start-fullscreen "http://localhost:5001" 2>/dev/null || \
    firefox "http://localhost:5001" 2>/dev/null || \
    xdg-open "http://localhost:5001" 2>/dev/null || \
    open "http://localhost:5001" 2>/dev/null) &

# Resolve Python interpreter: prefer venv, fall back to system python3/python
if [ -f "./venv/bin/python" ]; then
    PYTHON="./venv/bin/python"
elif [ -f "./venv/bin/python3" ]; then
    PYTHON="./venv/bin/python3"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PYTHON="python"
else
    echo -e "${YELLOW}ERROR: No Python interpreter found. Install Python 3 or create a venv.${NC}"
    exit 1
fi

echo -e "${GREEN}Launching server with: ${PYTHON}${NC}"
echo ""

$PYTHON web/app.py

echo ""
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}Dashboard stopped. Thanks for using Turtle Bot!${NC}"
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
