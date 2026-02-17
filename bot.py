"""
Telegram бот для сохранения заметок в Obsidian через GitHub
"""
import asyncio
import logging
import os
import tempfile
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from openai import OpenAI

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

# Инициализация OpenAI клиента (если API key указан)
openai_client = None
if config.OPENAI_API_KEY:
    openai_client = OpenAI(api_key=config.OPENAI_API_KEY)


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
    
    voice_status = "✅ доступна" if openai_client else "❌ недоступна"
    await message.answer(
        "👋 Привет! Я бот для сохранения заметок в Obsidian.\n\n"
        "📝 Отправь мне текстовое сообщение, и я сохраню его в твой Obsidian Vault через GitHub.\n"
        f"🎤 Транскрипция голосовых сообщений: {voice_status}\n\n"
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
    
    help_text = (
        "📝 Как использовать бота:\n\n"
        "**Текстовые сообщения:**\n"
        "1. Отправь мне любое текстовое сообщение\n"
        "2. Я создам файл в формате YYYY-MM-DD_HHmmss.md\n"
        "3. Файл будет сохранен в папке 00_Inbox твоего GitHub репозитория\n"
        "4. Obsidian Git автоматически синхронизирует изменения\n\n"
    )
    
    if openai_client:
        help_text += (
            "**Голосовые сообщения:**\n"
            "1. Отправь мне голосовое сообщение 🎤\n"
            "2. Я транскрибирую его через OpenAI Whisper\n"
            "3. Создам заметку с текстом и метаданными\n"
            "4. Файл: YYYY-MM-DD_HHmmss_voice.md\n\n"
        )
    else:
        help_text += (
            "**Голосовые сообщения:**\n"
            "❌ Транскрипция недоступна (нет OPENAI_API_KEY)\n\n"
        )
    
    help_text += (
        f"📁 Путь сохранения: {config.INBOX_PATH}/\n"
        "🏷️ Теги: [inbox, telegram] или [inbox, telegram, voice]"
    )
    
    await message.answer(help_text)


@dp.message(lambda message: message.voice is not None)
async def handle_voice_message(message: Message):
    """
    Обработчик голосовых сообщений
    
    Args:
        message: Объект сообщения от Telegram
    """
    # Проверка авторизации
    if not is_authorized(message.from_user.id):
        logger.warning(
            f"Неавторизованная попытка отправки голосового сообщения от пользователя "
            f"{message.from_user.id} (@{message.from_user.username})"
        )
        return
    
    # Проверка наличия OpenAI API key
    if not openai_client:
        await message.answer(
            "❌ Транскрипция голосовых сообщений недоступна.\n"
            "OpenAI API key не настроен."
        )
        logger.error("Попытка транскрибировать голосовое сообщение без OpenAI API key")
        return
    
    logger.info(f"Получено голосовое сообщение от пользователя {message.from_user.id}")
    
    # Отправка уведомления о начале обработки
    status_message = await message.answer("🎤 Транскрибирую голосовое сообщение...")
    
    temp_file_path = None
    
    try:
        # Получение информации о голосовом файле
        voice = message.voice
        duration = voice.duration
        
        # Создание временного файла для сохранения аудио
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_file:
            temp_file_path = temp_file.name
            
            # Скачивание голосового сообщения
            await bot.download(voice.file_id, destination=temp_file_path)
            logger.info(f"Голосовое сообщение скачано: {temp_file_path}")
        
        # Обновление статуса
        await status_message.edit_text("🔄 Распознаю речь...")
        
        # Транскрибация через OpenAI Whisper API
        with open(temp_file_path, 'rb') as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ru"  # Можно добавить автоопределение языка
            )
        
        transcribed_text = transcript.text
        logger.info(f"Транскрипция выполнена успешно. Длина текста: {len(transcribed_text)}")
        
        # Обновление статуса
        await status_message.edit_text("💾 Сохраняю заметку...")
        
        # Создание заметки в GitHub
        success, result_message = github_handler.create_voice_note(
            transcribed_text=transcribed_text,
            duration=duration,
            language="ru"
        )
        
        # Формирование итогового сообщения с превью транскрипции
        if success:
            preview = transcribed_text[:100] + "..." if len(transcribed_text) > 100 else transcribed_text
            final_message = (
                f"{result_message}\n\n"
                f"📝 Транскрипция:\n{preview}\n\n"
                f"⏱ Длительность: {duration}с"
            )
        else:
            final_message = result_message
        
        # Обновление статусного сообщения
        await status_message.edit_text(final_message)
        
        if success:
            logger.info(f"Голосовая заметка успешно сохранена для пользователя {message.from_user.id}")
        else:
            logger.error(f"Ошибка при сохранении голосовой заметки: {result_message}")
            
    except Exception as e:
        error_message = f"❌ Ошибка при обработке голосового сообщения: {str(e)}"
        await status_message.edit_text(error_message)
        logger.error(f"Необработанная ошибка при транскрибации: {e}", exc_info=True)
    
    finally:
        # Удаление временного файла
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"Временный файл удален: {temp_file_path}")
            except Exception as e:
                logger.error(f"Ошибка при удалении временного файла: {e}")


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
