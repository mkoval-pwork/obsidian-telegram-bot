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

# OpenAI настройки
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Smart Processing настройки
SMART_PROCESSING_ENABLED = os.getenv('SMART_PROCESSING_ENABLED', 'true').lower() == 'true'
SMART_PROCESSING_MODEL = os.getenv('SMART_PROCESSING_MODEL', 'gpt-4o-mini')
SMART_PROCESSING_TEMPERATURE = float(os.getenv('SMART_PROCESSING_TEMPERATURE', '0.3'))
SMART_PROCESSING_MAX_TOKENS = int(os.getenv('SMART_PROCESSING_MAX_TOKENS', '500'))

# Rate limiting для LLM
MAX_LLM_REQUESTS_PER_HOUR = int(os.getenv('MAX_LLM_REQUESTS_PER_HOUR', '20'))

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

# OpenAI API необязателен, но нужен для транскрипции голосовых сообщений
if not OPENAI_API_KEY:
    print("⚠️ OPENAI_API_KEY не установлен - голосовые сообщения и Smart Processing не будут работать")
elif SMART_PROCESSING_ENABLED:
    print(f"✅ Smart Processing включен (модель: {SMART_PROCESSING_MODEL})")
