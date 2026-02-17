"""
Модуль для интерактивного взаимодействия с пользователем через Inline Buttons
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from dataclasses import dataclass

from aiogram import Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from llm_processor import ProcessingResult

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
        voice_metadata: Optional[dict] = None
    ) -> None:
        """
        Показать превью обработанной заметки с inline кнопками
        
        Args:
            message: Исходное сообщение от пользователя
            result: Результат обработки через LLM
            original_text: Исходный текст заметки
            is_voice: Флаг голосового сообщения
            voice_metadata: Метаданные голосового (duration, language)
        """
        # Создание сессии
        session = ProcessingSession(
            user_id=message.from_user.id,
            message_id=message.message_id,
            original_text=original_text,
            result=result,
            created_at=datetime.now(),
            is_voice=is_voice,
            voice_metadata=voice_metadata
        )
        
        # Сохранение сессии
        self.sessions[message.from_user.id] = session
        
        # Генерация текста превью
        preview_text = self._generate_preview_text(session)
        
        # Создание клавиатуры
        keyboard = self._create_inline_keyboard()
        
        # Отправка превью
        await message.answer(
            preview_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
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
        elif action == "edit_tags":
            await self._handle_edit_tags(callback, session)
        elif action == "edit_summary":
            await self._handle_edit_summary(callback, session)
        elif action == "edit_tasks":
            await self._handle_edit_tasks(callback, session)
        elif action == "regenerate":
            await self._handle_regenerate(callback, session)
        elif action == "save_raw":
            await self._handle_save_raw(callback, session)
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
            # Парсинг задач (по строкам)
            tasks = [line.strip() for line in new_value.split("\n") if line.strip()]
            session.result.action_items = tasks
        
        session.edited = True
        
        # Удаление режима редактирования
        del self.edit_mode[user_id]
        
        # Обновление превью
        preview_text = self._generate_preview_text(session)
        keyboard = self._create_inline_keyboard()
        
        await message.answer(
            f"✅ Обновлено!\n\n{preview_text}",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        return True
    
    def _generate_preview_text(self, session: ProcessingSession) -> str:
        """Генерация текста превью"""
        result = session.result
        
        tags_str = ", ".join(result.tags) if result.tags else "нет"
        tasks_count = len(result.action_items)
        tasks_str = "\n".join(f"- [ ] {task}" for task in result.action_items) if result.action_items else "нет"
        
        voice_info = ""
        if session.is_voice and session.voice_metadata:
            duration = session.voice_metadata.get("duration", 0)
            language = session.voice_metadata.get("language", "unknown")
            voice_info = f" 🎤 (Длительность: {duration}с, Язык: {language})"
        
        preview = f"""🤖 **Smart Processing завершена!**{voice_info}

📝 **Summary:** {result.summary}
🏷️ **Tags:** {tags_str}
✅ **Задачи:** {tasks_count}

--- **Превью заметки** ---
**Summary:** {result.summary}

### Содержание
{session.original_text[:300]}{"..." if len(session.original_text) > 300 else ""}

### Задачи
{tasks_str}
---

Выберите действие:"""
        
        return preview
    
    def _create_inline_keyboard(self) -> InlineKeyboardMarkup:
        """Создание inline клавиатуры"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Сохранить", callback_data="approve"),
                InlineKeyboardButton(text="✏️ Теги", callback_data="edit_tags")
            ],
            [
                InlineKeyboardButton(text="✏️ Резюме", callback_data="edit_summary"),
                InlineKeyboardButton(text="✏️ Задачи", callback_data="edit_tasks")
            ],
            [
                InlineKeyboardButton(text="🔄 Заново", callback_data="regenerate"),
                InlineKeyboardButton(text="❌ Как есть", callback_data="save_raw")
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
        
        # Удаление сессии
        del self.sessions[callback.from_user.id]
        
        await callback.message.edit_text(msg)
    
    async def _handle_edit_tags(self, callback: CallbackQuery, session: ProcessingSession):
        """Обработка: Редактировать теги"""
        self.edit_mode[callback.from_user.id] = "tags"
        
        current_tags = ", ".join(session.result.tags)
        
        await callback.answer()
        await callback.message.answer(
            f"✏️ **Редактирование тегов**\n\n"
            f"Текущие теги: `{current_tags}`\n\n"
            f"Отправьте новые теги через запятую (английский, lowercase):\n"
            f"Пример: `project, idea, urgent`",
            parse_mode="Markdown"
        )
    
    async def _handle_edit_summary(self, callback: CallbackQuery, session: ProcessingSession):
        """Обработка: Редактировать резюме"""
        self.edit_mode[callback.from_user.id] = "summary"
        
        await callback.answer()
        await callback.message.answer(
            f"✏️ **Редактирование резюме**\n\n"
            f"Текущее резюме: `{session.result.summary}`\n\n"
            f"Отправьте новое резюме (макс 200 символов):",
            parse_mode="Markdown"
        )
    
    async def _handle_edit_tasks(self, callback: CallbackQuery, session: ProcessingSession):
        """Обработка: Редактировать задачи"""
        self.edit_mode[callback.from_user.id] = "tasks"
        
        current_tasks = "\n".join(session.result.action_items) if session.result.action_items else "нет"
        
        await callback.answer()
        await callback.message.answer(
            f"✏️ **Редактирование задач**\n\n"
            f"Текущие задачи:\n{current_tasks}\n\n"
            f"Отправьте новые задачи (по одной на строку):\n"
            f"Пример:\n`Купить молоко\nПозвонить маме\nОтправить отчет`",
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
        preview_text = self._generate_preview_text(session)
        keyboard = self._create_inline_keyboard()
        
        await callback.message.edit_text(
            preview_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    async def _handle_save_raw(self, callback: CallbackQuery, session: ProcessingSession):
        """Обработка: Сохранить без обработки"""
        from github_handler import GitHubHandler
        
        await callback.answer("💾 Сохраняю без обработки...")
        
        gh_handler = GitHubHandler()
        
        if session.is_voice:
            success, msg = gh_handler.create_voice_note(
                transcribed_text=session.original_text,
                duration=session.voice_metadata.get("duration", 0),
                language=session.voice_metadata.get("language", "unknown"),
                processed=False
            )
        else:
            success, msg = gh_handler.create_note(
                message_text=session.original_text,
                processed=False
            )
        
        # Удаление сессии
        del self.sessions[callback.from_user.id]
        
        await callback.message.edit_text(msg)
