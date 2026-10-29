#!/bin/bash
# ══════════════════════════════════════════
# IHSG Alert Bot - VPS Deployment Script
# Jalankan di VPS (Ubuntu/Debian):
#   bash deploy_vps.sh
# ══════════════════════════════════════════

set -e
echo ""
echo "  IHSG Alert Bot - VPS Setup"
echo "  =========================="
echo ""

# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install Python
sudo apt install python3 python3-pip python3-venv -y

# 3. Create project directory
mkdir -p ~/ihsg-bot
cd ~/ihsg-bot

# 4. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 5. Install dependencies
pip install python-telegram-bot yfinance requests websocket-client pandas numpy python-dotenv

# 6. Prompt for .env
echo ""
echo "  Masukkan credentials:"
read -p "  Telegram Bot Token: " BOT_TOKEN
read -p "  Telegram Chat ID: " CHAT_ID
read -p "  iTick API Key: " ITICK_KEY

cat > .env << EOF
TELEGRAM_BOT_TOKEN=${BOT_TOKEN}
TELEGRAM_CHAT_ID=${CHAT_ID}
ITICK_API_KEY=${ITICK_KEY}
STOCKBIT_USERNAME=
STOCKBIT_PASSWORD=
EOF
echo "  [OK] .env created"

# 7. Copy Python files (should already be here)
echo ""
echo "  Pastikan file .py sudah ada di ~/ihsg-bot/"
echo "  (config.py, indicators.py, data_fetcher.py,"
echo "   screener.py, telegram_bot.py, main.py)"
echo ""

# 8. Create systemd service
sudo tee /etc/systemd/system/ihsg-bot.service << EOF
[Unit]
Description=IHSG Strong Buy Alert Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/ihsg-bot
ExecStart=$HOME/ihsg-bot/venv/bin/python main.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 9. Enable and start
sudo systemctl daemon-reload
sudo systemctl enable ihsg-bot
sudo systemctl start ihsg-bot

echo ""
echo "  =========================="
echo "  DEPLOY COMPLETE!"
echo "  =========================="
echo ""
echo "  Bot is running as a system service."
echo "  Commands:"
echo "    sudo systemctl status ihsg-bot    # Check status"
echo "    sudo systemctl restart ihsg-bot   # Restart"
echo "    sudo systemctl stop ihsg-bot      # Stop"
echo "    journalctl -u ihsg-bot -f         # View logs"
echo ""
echo "  Bot will auto-restart if it crashes,"
echo "  and auto-start when VPS reboots."
echo ""
