#!/bin/bash
# Turtle Bot Web Dashboard Launcher

cd "$(dirname "$0")"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

echo ""
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${PURPLE}                    🐢 TURTLE BOT WEB DASHBOARD                          ${NC}"
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}📊 Starting web dashboard...${NC}"
echo -e "${CYAN}🌐 Dashboard will open at: ${GREEN}http://localhost:5001${NC}"
echo ""

# Wait a moment for the message to display
sleep 1

# Open browser in FULLSCREEN after a short delay (in background)
(sleep 3 && google-chrome --start-fullscreen "http://localhost:5001" 2>/dev/null || firefox --kiosk "http://localhost:5001" 2>/dev/null || xdg-open "http://localhost:5001" 2>/dev/null) &

# Start the Flask server
echo -e "${GREEN}✨ Launching server...${NC}"
echo ""

./venv/bin/python web/app.py

echo ""
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}Dashboard stopped. Thanks for using Turtle Bot!${NC}"
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
