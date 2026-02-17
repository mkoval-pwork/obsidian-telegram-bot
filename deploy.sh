#!/bin/bash
# Автоматический деплой бота на VPS

echo "========================================="
echo "  Obsidian Telegram Bot - VPS Deploy"
echo "========================================="
echo ""

# Проверка операционной системы
if ! grep -q "Ubuntu" /etc/os-release 2>/dev/null; then
    echo "⚠️  Внимание: Скрипт оптимизирован для Ubuntu"
fi

# Обновление системы
echo "📦 Обновление системы..."
apt update && apt upgrade -y

# Установка необходимых пакетов
echo "🔧 Установка Python, Git и зависимостей..."
apt install -y python3 python3-pip python3-venv git curl

# Проверка Python версии
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "✅ Python $PYTHON_VERSION установлен"

# Проверка наличия .env файла
if [ ! -f ".env" ]; then
    echo ""
    echo "❌ Файл .env не найден!"
    echo ""
    echo "Создайте файл .env с вашими токенами:"
    echo "nano .env"
    echo ""
    echo "Пример содержимого:"
    echo "TELEGRAM_BOT_TOKEN=ваш_токен"
    echo "ALLOWED_USER_ID=ваш_id"
    echo "GITHUB_TOKEN=ваш_github_токен"
    echo "GITHUB_REPO=username/repository"
    echo ""
    exit 1
fi

echo "✅ Файл .env найден"

# Выбор метода деплоя
echo ""
echo "Выберите метод запуска:"
echo "1) Docker (рекомендуется)"
echo "2) Python + Screen"
echo ""
read -p "Ваш выбор (1 или 2): " choice

if [ "$choice" == "1" ]; then
    # Docker деплой
    echo ""
    echo "🐳 Установка Docker..."
    
    if ! command -v docker &> /dev/null; then
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        rm get-docker.sh
        echo "✅ Docker установлен"
    else
        echo "✅ Docker уже установлен"
    fi
    
    echo ""
    echo "🚀 Сборка и запуск контейнера..."
    docker-compose down 2>/dev/null
    docker-compose up -d --build
    
    echo ""
    echo "✅ Бот запущен в Docker!"
    echo ""
    echo "Полезные команды:"
    echo "  docker-compose logs -f obsidian-bot  # Просмотр логов"
    echo "  docker-compose restart               # Перезапуск"
    echo "  docker-compose stop                  # Остановка"
    echo ""
    
    # Показать логи
    sleep 2
    echo "Логи бота (Ctrl+C для выхода):"
    docker-compose logs -f obsidian-bot

elif [ "$choice" == "2" ]; then
    # Screen деплой
    echo ""
    echo "📦 Установка screen..."
    apt install -y screen
    
    echo ""
    echo "📥 Установка Python зависимостей..."
    pip3 install -r requirements.txt
    
    echo ""
    echo "🚀 Запуск бота в screen..."
    
    # Остановить старую сессию если есть
    screen -X -S obsidian-bot quit 2>/dev/null
    
    # Создать новую сессию
    screen -dmS obsidian-bot python3 bot.py
    
    sleep 2
    
    if screen -list | grep -q "obsidian-bot"; then
        echo "✅ Бот запущен в screen!"
        echo ""
        echo "Полезные команды:"
        echo "  screen -r obsidian-bot    # Подключиться к боту"
        echo "  screen -ls                # Список сессий"
        echo "  Ctrl+A, затем D           # Отключиться (бот продолжит работать)"
        echo ""
    else
        echo "❌ Ошибка запуска. Попробуйте вручную:"
        echo "screen -S obsidian-bot"
        echo "python3 bot.py"
    fi
else
    echo "❌ Неверный выбор"
    exit 1
fi
