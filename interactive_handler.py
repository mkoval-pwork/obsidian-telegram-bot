"""
Модуль для интерактивного взаимодействия с пользователем через Inline Buttons
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from dataclasses import dataclass

from aiogram import Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from llm_processor import ProcessingResult, ActionItem

# Настройка логирования
logger = logging.getLogger(__name__)


@dataclass
class ProcessingSession:
    """Сессия обработки одной заметки"""
    user_id: int
    message_id: int
    original_text: str
    result: ProcessingResult
    created_at: datetime
    edited: bool = False
    is_voice: bool = False
    voice_metadata: Optional[dict] = None
    status_message_id: Optional[int] = None  # ID статусного сообщения для удаления
    preview_message_id: Optional[int] = None  # ID превью сообщения для удаления
    
    def is_expired(self, timeout_minutes: int = 10) -> bool:
        """Проверка истечения сессии"""
        return datetime.now() - self.created_at > timedelta(minutes=timeout_minutes)


class InteractiveHandler:
    """Обработчик интерактивного взаимодействия через Inline Buttons"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.sessions: Dict[int, ProcessingSession] = {}
        self.edit_mode: Dict[int, str] = {}  # user_id -> field_name
        
    async def show_processing_preview(
        self,
        message: Message,
        result: ProcessingResult,
        original_text: str,
        is_voice: bool = False,
        voice_metadata: Optional[dict] = None,
        status_message_id: Optional[int] = None
    ) -> None:
        """
        Показать превью обработанной заметки с inline кнопками
        
        Args:
            message: Исходное сообщение от пользователя
            result: Результат обработки через LLM
            original_text: Исходный текст заметки
            is_voice: Флаг голосового сообщения
            voice_metadata: Метаданные голосового (duration, language)
            status_message_id: ID статусного сообщения для последующего удаления
        """
        # Генерация текста превью
        preview_text = self._generate_preview_text_simple(result, is_voice, voice_metadata)
        
        # Создание клавиатуры
        keyboard = self._create_inline_keyboard()
        
        # Отправка превью
        preview_message = await message.answer(
            preview_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        # Создание сессии
        session = ProcessingSession(
            user_id=message.from_user.id,
            message_id=message.message_id,
            original_text=original_text,
            result=result,
            created_at=datetime.now(),
            is_voice=is_voice,
            voice_metadata=voice_metadata,
            status_message_id=status_message_id,
            preview_message_id=preview_message.message_id
        )
        
        # Сохранение сессии
        self.sessions[message.from_user.id] = session
    
    async def handle_callback(
        self,
        callback: CallbackQuery
    ) -> None:
        """
        Обработка нажатия на inline кнопку
        
        Args:
            callback: Callback query от Telegram
        """
        user_id = callback.from_user.id
        action = callback.data
        
        # Проверка наличия сессии
        session = self.sessions.get(user_id)
        if not session:
            await callback.answer("⚠️ Сессия истекла. Отправьте заметку заново.")
            return
        
        # Проверка истечения сессии
        if session.is_expired():
            del self.sessions[user_id]
            await callback.answer("⚠️ Сессия истекла (10 минут). Отправьте заметку заново.")
            return
        
        # Обработка действий
        if action == "approve":
            await self._handle_approve(callback, session)
        elif action == "edit_tasks":
            await self._handle_edit_tasks(callback, session)
        elif action == "regenerate":
            await self._handle_regenerate(callback, session)
        elif action == "delete":
            await self._handle_delete(callback, session)
        else:
            await callback.answer("❌ Неизвестное действие")
    
    async def handle_edit_response(
        self,
        message: Message
    ) -> bool:
        """
        Обработка ответа пользователя в режиме редактирования
        
        Args:
            message: Сообщение с новым значением поля
            
        Returns:
            True если сообщение было обработано как редактирование
        """
        user_id = message.from_user.id
        
        # Проверка режима редактирования
        if user_id not in self.edit_mode:
            return False  # Не в режиме редактирования
        
        field_name = self.edit_mode[user_id]
        session = self.sessions.get(user_id)
        
        if not session:
            del self.edit_mode[user_id]
            await message.answer("⚠️ Сессия истекла")
            return True
        
        # Обновление поля
        new_value = message.text.strip()
        
        if field_name == "tags":
            # Парсинг тегов (через запятую)
            tags = [tag.strip().lower().replace(" ", "-") for tag in new_value.split(",")]
            session.result.tags = tags
        elif field_name == "summary":
            session.result.summary = new_value[:200]
        elif field_name == "tasks":
            # Парсинг задач (по строкам) с сохранением существующих дат/времени
            tasks = []
            for i, line in enumerate(new_value.split("\n")):
                line = line.strip()
                if line:
                    # Если есть старая задача с тем же индексом, сохраняем её временные данные
                    if i < len(session.result.action_items):
                        old_task = session.result.action_items[i]
                        tasks.append(ActionItem(
                            text=line,
                            date=old_task.date,
                            time=old_task.time,
                            priority=old_task.priority,
                            tags=old_task.tags
                        ))
                    else:
                        # Новая задача без временных данных
                        tasks.append(ActionItem(text=line))
            session.result.action_items = tasks
        
        session.edited = True
        
        # Удаление режима редактирования
        del self.edit_mode[user_id]
        
        # Обновление превью
        preview_text = self._generate_preview_text_simple(session.result, session.is_voice, session.voice_metadata)
        keyboard = self._create_inline_keyboard()
        
        await message.answer(
            f"✅ Обновлено!\n\n{preview_text}",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        return True
    
    def _generate_preview_text_simple(self, result: ProcessingResult, is_voice: bool = False, 
                                      voice_metadata: Optional[dict] = None) -> str:
        """Генерация компактного текста превью"""
        tags_str = ", ".join(result.tags) if result.tags else "нет"
        tasks_count = len(result.action_items)
        
        # Используем метод to_markdown() для форматирования задач с датами
        tasks_str = "\n".join(task.to_markdown() for task in result.action_items) if result.action_items else "нет"
        
        voice_info = ""
        if is_voice and voice_metadata:
            duration = voice_metadata.get("duration", 0)
            language = voice_metadata.get("language", "russian")
            voice_info = f" 🎤 ({duration}с, {language})"
        
        # Информация о датах (если есть)
        dates_info = ""
        if result.dates_mentioned:
            dates_count = len(result.dates_mentioned)
            dates_info = f"\n📅 **Упомянутые даты:** {dates_count}"
        
        preview = f"""🤖 **Smart Processing v{result.processing_version} завершена!**{voice_info}

📝 **Summary:** {result.summary}
🏷️ **Tags:** {tags_str}
✅ **Задачи:** {tasks_count}{dates_info}

{tasks_str}

Выберите действие:"""
        
        return preview
    
    def _create_inline_keyboard(self) -> InlineKeyboardMarkup:
        """Создание упрощенной inline клавиатуры"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Сохранить", callback_data="approve"),
                InlineKeyboardButton(text="✏️ Задачи", callback_data="edit_tasks")
            ],
            [
                InlineKeyboardButton(text="🔄 Перегенерировать", callback_data="regenerate"),
                InlineKeyboardButton(text="🗑️ Удалить", callback_data="delete")
            ]
        ])
        return keyboard
    
    async def _handle_approve(self, callback: CallbackQuery, session: ProcessingSession):
        """Обработка: Сохранить как есть"""
        from github_handler import GitHubHandler
        
        await callback.answer("💾 Сохраняю...")
        
        gh_handler = GitHubHandler()
        
        if session.is_voice:
            success, msg = gh_handler.create_voice_note(
                transcribed_text=session.original_text,
                duration=session.voice_metadata.get("duration", 0),
                language=session.voice_metadata.get("language", "unknown"),
                processed=True,
                processing_result=session.result
            )
        else:
            success, msg = gh_handler.create_note(
                message_text=session.original_text,
                processed=True,
                processing_result=session.result
            )
        
        # Удаление промежуточных сообщений
        await self._cleanup_messages(session, callback.message.chat.id)
        
        # Короткое финальное саммари
        final_msg = self._generate_final_summary(session, success)
        await self.bot.send_message(callback.message.chat.id, final_msg, parse_mode="Markdown")
        
        # Удаление сессии
        del self.sessions[callback.from_user.id]
    
    async def _cleanup_messages(self, session: ProcessingSession, chat_id: int):
        """Удаление промежуточных сообщений"""
        try:
            # Удаление статусного сообщения
            if session.status_message_id:
                try:
                    await self.bot.delete_message(chat_id, session.status_message_id)
                except Exception as e:
                    logger.debug(f"Не удалось удалить статусное сообщение: {e}")
            
            # Удаление превью сообщения
            if session.preview_message_id:
                try:
                    await self.bot.delete_message(chat_id, session.preview_message_id)
                except Exception as e:
                    logger.debug(f"Не удалось удалить превью сообщение: {e}")
        except Exception as e:
            logger.error(f"Ошибка при удалении сообщений: {e}")
    
    def _generate_final_summary(self, session: ProcessingSession, success: bool) -> str:
        """Генерация короткого финального саммари"""
        if not success:
            return "❌ Ошибка при сохранении заметки"
        
        result = session.result
        tasks_count = len(result.action_items)
        tags_count = len(result.tags)
        
        # Получение даты для имени файла
        today = datetime.now().strftime("%Y-%m-%d")
        
        voice_emoji = "🎤 " if session.is_voice else ""
        
        summary = (
            f"✅ {voice_emoji}Сохранено в `{today}.md`\n"
            f"📝 {result.summary[:60]}...\n"
            f"📊 {tasks_count} задач, {tags_count} тегов"
        )
        
        return summary
    
    async def _handle_edit_tasks(self, callback: CallbackQuery, session: ProcessingSession):
        """Обработка: Редактировать задачи"""
        self.edit_mode[callback.from_user.id] = "tasks"
        
        # Показываем текущие задачи с markdown форматированием (с датами)
        current_tasks = "\n".join(task.to_markdown() for task in session.result.action_items) if session.result.action_items else "нет"
        
        await callback.answer()
        await callback.message.answer(
            f"✏️ **Редактирование задач**\n\n"
            f"Текущие задачи:\n{current_tasks}\n\n"
            f"Отправьте новые задачи (по одной на строку):\n"
            f"Пример:\n`Купить молоко\nПозвонить маме\nОтправить отчет`\n\n"
            f"ℹ️ _Даты и время из старых задач будут сохранены_",
            parse_mode="Markdown"
        )
    
    async def _handle_regenerate(self, callback: CallbackQuery, session: ProcessingSession):
        """Обработка: Перегенерировать через LLM"""
        from llm_processor import process_text
        
        await callback.answer("🔄 Обрабатываю заново...")
        await callback.message.edit_text("🤖 Обрабатываю через AI...")
        
        # Определение языка
        language = "ru"
        if session.is_voice and session.voice_metadata:
            language = session.voice_metadata.get("language", "ru")
        
        # Повторная обработка
        new_result = await process_text(session.original_text, language)
        
        if not new_result.success:
            await callback.message.edit_text(
                f"❌ Ошибка при обработке: {new_result.error_message}\n\n"
                f"Попробуйте еще раз или сохраните без обработки."
            )
            return
        
        # Обновление сессии
        session.result = new_result
        
        # Показать новое превью
        preview_text = self._generate_preview_text_simple(session.result, session.is_voice, session.voice_metadata)
        keyboard = self._create_inline_keyboard()
        
        await callback.message.edit_text(
            preview_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    async def _handle_delete(self, callback: CallbackQuery, session: ProcessingSession):
        """Обработка: Удалить заметку (отменить сохранение)"""
        await callback.answer("🗑️ Удалено")
        
        # Удаление промежуточных сообщений
        await self._cleanup_messages(session, callback.message.chat.id)
        
        # Короткое уведомление
        await self.bot.send_message(
            callback.message.chat.id, 
            "🗑️ Заметка не сохранена"
        )
        
        # Удаление сессии
        del self.sessions[callback.from_user.id]
