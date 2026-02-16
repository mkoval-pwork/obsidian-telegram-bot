"""
Конфигурация бота
"""
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Telegram настройки
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ALLOWED_USER_ID = int(os.getenv('ALLOWED_USER_ID', 0))

# GitHub настройки
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPO = os.getenv('GITHUB_REPO')

# Путь для сохранения заметок в репозитории
INBOX_PATH = '00_Inbox'

# Проверка наличия обязательных переменных
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не установлен в .env файле")
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN не установлен в .env файле")
if not GITHUB_REPO:
    raise ValueError("GITHUB_REPO не установлен в .env файле")
if not ALLOWED_USER_ID:
    raise ValueError("ALLOWED_USER_ID не установлен в .env файле")
