#!/usr/bin/env bash
set -e

echo "=========================================================="
echo " Starting NEXUVER 24/7 Suite on Render Cloud"
echo "=========================================================="

# 1. Clean up old locks if any
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99

# 2. Launch Virtual Framebuffer Display (Xvfb) on display :99
echo "[Init] Launching Xvfb virtual 1920x1080 display on :99..."
Xvfb :99 -screen 0 1920x1080x24 -ac -nolisten tcp &
export DISPLAY=:99
sleep 2

# 3. Check Chromium / Chrome path
if which chromium >/dev/null 2>&1; then
    echo "[Init] Chromium found at: $(which chromium)"
    export CHROME_PATH="$(which chromium)"
elif which google-chrome >/dev/null 2>&1; then
    echo "[Init] Chrome found at: $(which google-chrome)"
    export CHROME_PATH="$(which google-chrome)"
fi

# 4. Start the Discord Bot & Web Server
echo "[Init] Starting bot.py..."
exec python bot.py

