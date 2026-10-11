#!/bin/bash
# Sri Valmiki Ramayana — Mac/Linux launcher
# Run: bash start.sh

cd "$(dirname "$0")"

echo ""
echo " ========================================"
echo "   Sri Valmiki Ramayana — Local Server"
echo " ========================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo " [ERROR] Python3 not found. Please install Python 3.10+"
    exit 1
fi

# Install dependencies
echo " [1/2] Checking dependencies..."
pip3 install -r requirements.txt -q

# Start server
echo " [2/2] Starting server..."
echo ""
echo " ----------------------------------------"
echo "  Open your browser and go to:"
echo "  http://localhost:5000"
echo ""
echo "  Username : admin"
echo "  Password : ramayana2024"
echo " ----------------------------------------"
echo ""
echo " Press Ctrl+C to stop."
echo ""

python3 server/api.py
