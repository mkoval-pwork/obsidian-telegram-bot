"""
Telegram бот для сохранения заметок в Obsidian через GitHub
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

import config
from github_handler import GitHubHandler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Инициализация GitHub обработчика
github_handler = GitHubHandler()


def is_authorized(user_id: int) -> bool:
    """
    Проверка авторизации пользователя
    
    Args:
        user_id: ID пользователя Telegram
        
    Returns:
        bool: True если пользователь авторизован
    """
    return user_id == config.ALLOWED_USER_ID


@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    if not is_authorized(message.from_user.id):
        logger.warning(f"Неавторизованный доступ от пользователя {message.from_user.id}")
        return
    
    await message.answer(
        "👋 Привет! Я бот для сохранения заметок в Obsidian.\n\n"
        "Просто отправь мне текстовое сообщение, и я сохраню его в твой Obsidian Vault через GitHub.\n\n"
        "Команды:\n"
        "/start - это сообщение\n"
        "/help - помощь"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    if not is_authorized(message.from_user.id):
        logger.warning(f"Неавторизованный доступ от пользователя {message.from_user.id}")
        return
    
    await message.answer(
        "📝 Как использовать бота:\n\n"
        "1. Отправь мне любое текстовое сообщение\n"
        "2. Я создам файл в формате YYYY-MM-DD_HHmmss.md\n"
        "3. Файл будет сохранен в папке 00_Inbox твоего GitHub репозитория\n"
        "4. Obsidian Git автоматически синхронизирует изменения\n\n"
        f"📁 Путь сохранения: {config.INBOX_PATH}/\n"
        "🏷️ Теги: [inbox, telegram]"
    )


@dp.message()
async def handle_text_message(message: Message):
    """
    Обработчик всех текстовых сообщений
    
    Args:
        message: Объект сообщения от Telegram
    """
    # Проверка авторизации
    if not is_authorized(message.from_user.id):
        logger.warning(
            f"Неавторизованная попытка отправки сообщения от пользователя "
            f"{message.from_user.id} (@{message.from_user.username})"
        )
        return
    
    # Проверка наличия текста в сообщении
    if not message.text:
        await message.answer("❌ Поддерживаются только текстовые сообщения")
        return
    
    logger.info(f"Получено сообщение от пользователя {message.from_user.id}")
    
    # Отправка уведомления о начале обработки
    status_message = await message.answer("⏳ Сохраняю заметку...")
    
    try:
        # Создание заметки в GitHub
        success, result_message = github_handler.create_note(message.text)
        
        # Обновление статусного сообщения
        await status_message.edit_text(result_message)
        
        if success:
            logger.info(f"Заметка успешно сохранена для пользователя {message.from_user.id}")
        else:
            logger.error(f"Ошибка при сохранении заметки: {result_message}")
            
    except Exception as e:
        error_message = f"❌ Произошла ошибка: {str(e)}"
        await status_message.edit_text(error_message)
        logger.error(f"Необработанная ошибка: {e}", exc_info=True)


async def main():
    """Главная функция запуска бота"""
    logger.info("Запуск бота...")
    
    # Проверка подключения к GitHub
    if github_handler.connect_to_repo():
        logger.info(f"✅ Подключение к GitHub репозиторию {config.GITHUB_REPO} успешно")
    else:
        logger.error("❌ Не удалось подключиться к GitHub репозиторию")
        logger.error("Проверьте правильность GITHUB_TOKEN и GITHUB_REPO в .env файле")
        return
    
    # Запуск бота
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
