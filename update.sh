#!/bin/bash
# Скрипт быстрого обновления бота на VPS

echo "========================================="
echo "  Obsidian Bot - Quick Update"
echo "========================================="
echo ""

cd "$(dirname "$0")" || exit 1

echo "📥 Pulling latest changes..."
git pull origin main

if [ $? -ne 0 ]; then
    echo "❌ Git pull failed!"
    exit 1
fi

echo ""
echo "🔄 Restarting bot..."

if [ -f "docker-compose.yml" ]; then
    # Docker mode
    docker-compose down
    docker-compose up -d --build
    
    echo ""
    echo "✅ Bot updated and restarted (Docker mode)"
    echo ""
    echo "📊 Container status:"
    docker-compose ps
    
    echo ""
    echo "📋 Recent logs (Ctrl+C to exit):"
    sleep 2
    docker-compose logs -f --tail=50 obsidian-bot
else
    # Screen mode
    screen -X -S obsidian-bot quit 2>/dev/null
    sleep 1
    
    pip3 install -r requirements.txt
    screen -dmS obsidian-bot python3 bot.py
    
    sleep 2
    
    if screen -list | grep -q "obsidian-bot"; then
        echo "✅ Bot updated and restarted (Screen mode)"
        echo ""
        echo "To view logs: screen -r obsidian-bot"
    else
        echo "❌ Failed to restart bot"
        exit 1
    fi
fi
