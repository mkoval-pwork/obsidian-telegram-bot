# Smart Processing - План реализации для AI-агента

**Версия:** 1.0  
**Дата:** 17.02.2026  
**Целевой исполнитель:** AI-агент (Claude)  
**Базовое ТЗ:** [SMART_PROCESSING_TZ.md](./SMART_PROCESSING_TZ.md)

---

## 📋 Цель документа

Этот документ содержит точные инструкции для AI-агента по реализации Smart Processing. Включает:
- Конкретные сигнатуры функций и классов
- Точный порядок выполнения с зависимостями
- Примеры кода для каждого модуля
- Тесты для проверки работоспособности
- Команды для запуска и проверки

---

## 🎯 Краткая сводка задачи

Реализовать интеллектуальную обработку заметок через LLM (OpenAI GPT-4o-mini):
1. **Извлечение:** теги (3-5), резюме (макс 200 символов), задачи (action items)
2. **Интерактивность:** Inline buttons для редактирования результатов
3. **Интеграция:** С существующим ботом (текст + голос)
4. **Надежность:** Retry логика, rate limiting, fallback

---

## 📦 Файлы для создания/изменения

### Новые файлы (создать):
1. `llm_processor.py` - Обработка через OpenAI API
2. `interactive_handler.py` - Inline buttons + редактирование

### Файлы для обновления:
3. `bot.py` - Добавить вызов Smart Processing
4. `github_handler.py` - Новый формат заметок
5. `config.py` - Новые настройки

---

## 🔧 Детальная спецификация модулей

### 1. llm_processor.py

#### Зависимости

```python
import json
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Optional, List
from openai import OpenAI, OpenAIError
import config
```

#### Dataclasses

```python
@dataclass
class ProcessingResult:
    """Результат обработки текста через LLM"""
    summary: str
    tags: List[str]
    action_items: List[str]
    success: bool
    error_message: Optional[str] = None
    processing_time: float = 0.0
    model_used: str = "gpt-4o-mini"
    
    def to_dict(self) -> dict:
        """Сериализация в dict"""
        return {
            "summary": self.summary,
            "tags": self.tags,
            "action_items": self.action_items,
            "success": self.success,
            "error_message": self.error_message,
            "processing_time": self.processing_time,
            "model_used": self.model_used
        }
```

#### Константы

```python
MAX_RETRIES = 3
BASE_WAIT_TIME = 2  # секунды для экспоненциальной задержки
MAX_TEXT_LENGTH = 10000  # максимальная длина текста для обработки

SYSTEM_PROMPT = """Ты - ассистент для обработки заметок в системе Personal Knowledge Management (Obsidian).
Твоя задача - проанализировать текст и извлечь структурированную информацию.

ВАЖНЫЕ ПРАВИЛА:
1. Извлекай только то, что явно присутствует в тексте
2. НЕ добавляй информацию от себя
3. Теги должны быть релевантны содержанию
4. Резюме должно быть информативным, но кратким
5. Задачи - только конкретные действия, которые упомянуты в тексте

ИЗВЛЕКАЙ:
1. ТЕГИ (tags): 
   - 3-5 релевантных тегов
   - Английский язык, lowercase
   - Формат: kebab-case (через дефис)
   - От общих к конкретным
   - Примеры: project-idea, meeting, task, shopping, health

2. РЕЗЮМЕ (summary):
   - Краткое описание (1-2 предложения)
   - Максимум 200 символов
   - На том же языке, что и текст
   - Фокус на ключевых идеях

3. ЗАДАЧИ (action_items):
   - Список конкретных действий
   - Только то, что упомянуто в тексте
   - Формат: глагол + объект + контекст
   - Если задач нет - пустой массив

ФОРМАТ ОТВЕТА (строго JSON):
{
  "summary": "Краткое описание содержания",
  "tags": ["tag1", "tag2", "tag3"],
  "action_items": ["Задача 1", "Задача 2"]
}

НЕ добавляй никакого текста кроме JSON!"""
```

#### Основные функции

```python
async def process_text(
    text: str, 
    language: str = "ru",
    client: Optional[OpenAI] = None
) -> ProcessingResult:
    """
    Основная функция обработки текста через LLM
    
    Args:
        text: Исходный текст для обработки
        language: Язык текста (для генерации summary на правильном языке)
        client: OpenAI клиент (если None - создается новый)
        
    Returns:
        ProcessingResult с извлеченными данными
        
    Example:
        >>> result = await process_text("Завтра купить молоко", "ru")
        >>> result.success
        True
        >>> result.tags
        ['shopping', 'groceries', 'todo']
    """
    import time
    start_time = time.time()
    
    # Валидация входных данных
    is_valid, error_msg = validate_text_for_processing(text)
    if not is_valid:
        return ProcessingResult(
            summary="",
            tags=[],
            action_items=[],
            success=False,
            error_message=error_msg
        )
    
    # Инициализация клиента
    if client is None:
        if not config.OPENAI_API_KEY:
            return ProcessingResult(
                summary="",
                tags=[],
                action_items=[],
                success=False,
                error_message="OPENAI_API_KEY не настроен"
            )
        client = OpenAI(api_key=config.OPENAI_API_KEY)
    
    # Вызов LLM с retry
    try:
        response_data = await _call_llm_with_retry(client, text, language)
        
        # Парсинг и валидация ответа
        if not _validate_response(response_data):
            return ProcessingResult(
                summary="",
                tags=[],
                action_items=[],
                success=False,
                error_message="LLM вернул некорректные данные"
            )
        
        processing_time = time.time() - start_time
        
        return ProcessingResult(
            summary=response_data.get("summary", ""),
            tags=response_data.get("tags", []),
            action_items=response_data.get("action_items", []),
            success=True,
            processing_time=processing_time,
            model_used=config.SMART_PROCESSING_MODEL
        )
        
    except Exception as e:
        logging.error(f"Unexpected error in process_text: {e}", exc_info=True)
        return ProcessingResult(
            summary="",
            tags=[],
            action_items=[],
            success=False,
            error_message=f"Неожиданная ошибка: {str(e)}"
        )


async def _call_llm_with_retry(
    client: OpenAI,
    text: str,
    language: str
) -> dict:
    """
    Вызов LLM с повторными попытками при ошибках
    
    Implements exponential backoff: wait_time = 2^attempt seconds
    
    Args:
        client: OpenAI клиент
        text: Текст для обработки
        language: Язык текста
        
    Returns:
        dict с извлеченными данными (summary, tags, action_items)
        
    Raises:
        Exception: После MAX_RETRIES неудачных попыток
    """
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            # Формирование промпта
            user_prompt = _create_user_prompt(text, language)
            
            # Вызов OpenAI API
            response = client.chat.completions.create(
                model=config.SMART_PROCESSING_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=config.SMART_PROCESSING_TEMPERATURE,
                max_tokens=config.SMART_PROCESSING_MAX_TOKENS,
                response_format={"type": "json_object"}  # Гарантирует JSON
            )
            
            # Парсинг ответа
            response_text = response.choices[0].message.content
            response_data = _parse_llm_response(response_text)
            
            logging.info(
                f"LLM processing successful on attempt {attempt + 1}",
                extra={"text_length": len(text), "model": config.SMART_PROCESSING_MODEL}
            )
            
            return response_data
            
        except OpenAIError as e:
            last_error = e
            logging.warning(f"OpenAI API error on attempt {attempt + 1}/{MAX_RETRIES}: {e}")
            
            if attempt < MAX_RETRIES - 1:
                wait_time = BASE_WAIT_TIME ** attempt
                logging.info(f"Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
        
        except Exception as e:
            last_error = e
            logging.error(f"Unexpected error on attempt {attempt + 1}/{MAX_RETRIES}: {e}")
            
            if attempt < MAX_RETRIES - 1:
                wait_time = BASE_WAIT_TIME ** attempt
                await asyncio.sleep(wait_time)
    
    # Все попытки исчерпаны
    error_msg = f"LLM processing failed after {MAX_RETRIES} attempts: {str(last_error)}"
    logging.error(error_msg)
    raise Exception(error_msg)


def _create_user_prompt(text: str, language: str) -> str:
    """
    Создание user prompt для LLM
    
    Args:
        text: Текст заметки
        language: Код языка (ru, en, uk, etc.)
        
    Returns:
        Отформатированный промпт
    """
    language_names = {
        "ru": "русский",
        "en": "английский",
        "uk": "украинский",
        "de": "немецкий",
        "fr": "французский",
        "es": "испанский",
        "it": "итальянский",
        "pt": "португальский"
    }
    
    lang_name = language_names.get(language, "исходный язык текста")
    
    return f"""Проанализируй следующий текст и извлеки структурированную информацию:

ТЕКСТ:
{text}

ТРЕБОВАНИЯ:
- Язык резюме: {lang_name}
- Теги: английский, lowercase, kebab-case
- Задачи: только явно упомянутые действия

Ответь в формате JSON."""


def _parse_llm_response(response: str) -> dict:
    """
    Парсинг JSON ответа от LLM
    
    Обрабатывает случаи, когда LLM добавляет текст до/после JSON
    
    Args:
        response: Текстовый ответ от LLM
        
    Returns:
        Распарсенный dict
        
    Raises:
        json.JSONDecodeError: Если не удалось распарсить JSON
    """
    try:
        # Попытка прямого парсинга
        return json.loads(response)
    except json.JSONDecodeError:
        # Поиск JSON в тексте
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        
        if json_start == -1 or json_end == 0:
            raise json.JSONDecodeError("No JSON found in response", response, 0)
        
        json_str = response[json_start:json_end]
        return json.loads(json_str)


def _validate_response(response_data: dict) -> bool:
    """
    Валидация структуры ответа от LLM
    
    Args:
        response_data: Распарсенный ответ
        
    Returns:
        True если структура валидна
    """
    required_keys = {"summary", "tags", "action_items"}
    
    if not all(key in response_data for key in required_keys):
        return False
    
    if not isinstance(response_data["summary"], str):
        return False
    
    if not isinstance(response_data["tags"], list):
        return False
    
    if not isinstance(response_data["action_items"], list):
        return False
    
    # Проверка длины резюме
    if len(response_data["summary"]) > 250:  # 200 + буфер
        response_data["summary"] = response_data["summary"][:200]
    
    # Проверка тегов (должны быть строками, lowercase, без пробелов)
    response_data["tags"] = [
        tag.lower().replace(" ", "-") 
        for tag in response_data["tags"] 
        if isinstance(tag, str)
    ][:5]  # Максимум 5 тегов
    
    return True


def validate_text_for_processing(text: str) -> tuple[bool, str]:
    """
    Валидация текста перед отправкой в LLM
    
    Args:
        text: Текст для проверки
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not text or not text.strip():
        return False, "Пустой текст"
    
    if len(text) > MAX_TEXT_LENGTH:
        return False, f"Текст слишком длинный (макс {MAX_TEXT_LENGTH} символов)"
    
    return True, "OK"
```

#### Пример использования

```python
# Пример 1: Простая обработка
result = await process_text("Завтра купить молоко и позвонить маме", "ru")
print(result.summary)  # "Список покупок и напоминание"
print(result.tags)     # ['shopping', 'family', 'todo']
print(result.action_items)  # ['Купить молоко', 'Позвонить маме']

# Пример 2: Обработка с ошибкой
result = await process_text("", "ru")
print(result.success)  # False
print(result.error_message)  # "Пустой текст"
```

---

### 2. interactive_handler.py

#### Зависимости

```python
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from dataclasses import dataclass
from aiogram import Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from llm_processor import ProcessingResult
```

#### Классы

```python
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
    ) -> None:
        """
        Обработка ответа пользователя в режиме редактирования
        
        Args:
            message: Сообщение с новым значением поля
        """
        user_id = message.from_user.id
        
        # Проверка режима редактирования
        if user_id not in self.edit_mode:
            return  # Не в режиме редактирования
        
        field_name = self.edit_mode[user_id]
        session = self.sessions.get(user_id)
        
        if not session:
            del self.edit_mode[user_id]
            await message.answer("⚠️ Сессия истекла")
            return
        
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
```

#### Пример использования

```python
# Инициализация
handler = InteractiveHandler(bot)

# Показать превью
await handler.show_processing_preview(
    message=message,
    result=processing_result,
    original_text="Завтра купить молоко"
)

# Обработка callback (регистрируется в bot.py)
@dp.callback_query()
async def handle_callbacks(callback: CallbackQuery):
    await interactive_handler.handle_callback(callback)
```

---

### 3. Обновление bot.py

#### Изменения в импортах

```python
# ДОБАВИТЬ в начало файла
from llm_processor import process_text, ProcessingResult
from interactive_handler import InteractiveHandler

# Инициализация interactive handler (после создания bot)
interactive_handler = InteractiveHandler(bot)

# Rate limiting для LLM
llm_requests = defaultdict(list)
```

#### Новая функция rate limiting

```python
def check_llm_rate_limit(user_id: int) -> tuple[bool, int]:
    """
    Проверка rate limit для LLM запросов
    
    Args:
        user_id: ID пользователя Telegram
        
    Returns:
        tuple: (разрешено, количество оставшихся запросов)
    """
    now = datetime.now()
    hour_ago = now - timedelta(hours=1)
    
    # Очищаем старые запросы
    llm_requests[user_id] = [t for t in llm_requests[user_id] if t > hour_ago]
    
    current_count = len(llm_requests[user_id])
    
    if current_count >= config.MAX_LLM_REQUESTS_PER_HOUR:
        return False, 0
    
    # Регистрируем текущий запрос
    llm_requests[user_id].append(now)
    remaining = config.MAX_LLM_REQUESTS_PER_HOUR - current_count - 1
    
    return True, remaining
```

#### Изменения в handle_text_message()

```python
@dp.message()
async def handle_text_message(message: Message):
    """Обработчик текстовых сообщений"""
    
    # ... существующая проверка авторизации ...
    if not is_authorized(message.from_user.id):
        logger.warning(f"Неавторизованный доступ от {message.from_user.id}")
        return
    
    if not message.text:
        await message.answer("❌ Поддерживаются только текстовые сообщения")
        return
    
    logger.info(f"Получено сообщение от пользователя {message.from_user.id}")
    
    status_message = await message.answer("⏳ Сохраняю заметку...")
    
    try:
        # НОВОЕ: Smart Processing
        if config.SMART_PROCESSING_ENABLED:
            # Проверка rate limit
            allowed, remaining = check_llm_rate_limit(message.from_user.id)
            
            if not allowed:
                await status_message.edit_text(
                    f"⏸ Превышен лимит AI обработки.\n"
                    f"Максимум: {config.MAX_LLM_REQUESTS_PER_HOUR} запросов в час.\n"
                    f"Заметка будет сохранена без обработки."
                )
                # Fallback: сохранить без обработки
                success, result_message = github_handler.create_note(
                    message.text,
                    processed=False
                )
                await status_message.edit_text(result_message)
                return
            
            # Обработка через LLM
            await status_message.edit_text("🤖 Обрабатываю через AI...")
            
            result = await process_text(
                text=message.text,
                language="ru"  # TODO: определять язык автоматически
            )
            
            if result.success:
                # Показать интерактивное превью
                await interactive_handler.show_processing_preview(
                    message=message,
                    result=result,
                    original_text=message.text,
                    is_voice=False
                )
                await status_message.delete()
                
                logger.info(
                    f"Smart Processing successful. Remaining requests: {remaining}",
                    extra={"user_id": message.from_user.id}
                )
                return
            else:
                # LLM failed - fallback
                logger.warning(f"LLM processing failed: {result.error_message}")
                await status_message.edit_text(
                    f"⚠️ Не удалось обработать через AI: {result.error_message}\n"
                    f"Сохраняю заметку без обработки..."
                )
        
        # Fallback: сохранить без обработки
        success, result_message = github_handler.create_note(
            message.text,
            processed=False
        )
        
        await status_message.edit_text(result_message)
        
        if success:
            logger.info(f"Заметка сохранена (без обработки) для {message.from_user.id}")
        else:
            logger.error(f"Ошибка сохранения: {result_message}")
            
    except Exception as e:
        error_message = f"❌ Произошла ошибка: {str(e)}"
        await status_message.edit_text(error_message)
        logger.error(f"Необработанная ошибка: {e}", exc_info=True)
```

#### Новый обработчик callback queries

```python
@dp.callback_query()
async def handle_callback_queries(callback: CallbackQuery):
    """Обработчик нажатий на inline кнопки"""
    await interactive_handler.handle_callback(callback)
```

#### Изменения в handle_voice_message()

Аналогичные изменения, но с передачей метаданных голосового сообщения:

```python
# После успешной транскрибации добавить:
if config.SMART_PROCESSING_ENABLED:
    # ... аналогичная логика, но с is_voice=True и voice_metadata
    await interactive_handler.show_processing_preview(
        message=message,
        result=result,
        original_text=transcribed_text,
        is_voice=True,
        voice_metadata={
            "duration": duration,
            "language": detected_language
        }
    )
```

---

### 4. Обновление github_handler.py

#### Изменения в сигнатурах

```python
def create_note(
    self, 
    message_text: str,
    processed: bool = False,
    processing_result: Optional['ProcessingResult'] = None
) -> tuple[bool, str]:
    """
    Создание заметки с поддержкой Smart Processing
    
    Args:
        message_text: Исходный текст заметки
        processed: Флаг обработки через LLM
        processing_result: Результат обработки (если processed=True)
        
    Returns:
        tuple: (успех, сообщение для пользователя)
    """
    # ... существующая логика подключения к репо ...
    
    try:
        now = datetime.now()
        filename = now.strftime("%Y-%m-%d.md")
        file_path = f"{config.INBOX_PATH}/{filename}"
        time_formatted = now.strftime("%H:%M")
        
        # НОВОЕ: Формирование контента в зависимости от processed
        if processed and processing_result:
            new_note = self._format_processed_note(
                time_formatted=time_formatted,
                message_text=message_text,
                result=processing_result,
                is_voice=False
            )
            tags = ["inbox", "telegram"] + processing_result.tags
        else:
            new_note = f"\n## {time_formatted}\n\n{message_text}\n"
            tags = ["inbox", "telegram", "unprocessed"] if processed is False else ["inbox", "telegram"]
        
        # ... остальная логика создания/обновления файла ...
        
        # При создании нового файла:
        if processed and processing_result:
            content = self._format_new_daily_file_processed(
                date_formatted=now.strftime("%Y-%m-%d"),
                date_display=now.strftime("%d.%m.%Y"),
                time_formatted=time_formatted,
                message_text=message_text,
                result=processing_result,
                tags=tags,
                is_voice=False
            )
        else:
            # ... существующий формат ...
            pass
        
        # ... коммит в GitHub ...
        
    except Exception as e:
        # ... обработка ошибок ...
        pass
```

#### Новые вспомогательные методы

```python
def _format_processed_note(
    self,
    time_formatted: str,
    message_text: str,
    result: 'ProcessingResult',
    is_voice: bool = False,
    voice_metadata: Optional[dict] = None
) -> str:
    """
    Форматирование обработанной заметки для добавления в файл
    
    Args:
        time_formatted: Время в формате HH:MM
        message_text: Исходный текст
        result: Результат обработки LLM
        is_voice: Флаг голосового сообщения
        voice_metadata: Метаданные голосового (если is_voice=True)
        
    Returns:
        Отформатированная строка заметки
    """
    voice_emoji = " 🎤" if is_voice else ""
    
    tasks_section = ""
    if result.action_items:
        tasks_str = "\n".join(f"- [ ] {task}" for task in result.action_items)
        tasks_section = f"\n\n### Задачи\n\n{tasks_str}"
    
    source_info = "Telegram"
    if is_voice and voice_metadata:
        duration = voice_metadata.get("duration", 0)
        language = voice_metadata.get("language", "unknown")
        source_info = f"Telegram Voice Message • Длительность: {duration}с • Язык: {language}"
    
    note = f"""
## {time_formatted}{voice_emoji}

**Summary:** {result.summary}

### Содержание

{message_text}{tasks_section}

---
*Источник: {source_info} | Обработано: Smart Processing ({result.model_used})*
"""
    
    return note


def _format_new_daily_file_processed(
    self,
    date_formatted: str,
    date_display: str,
    time_formatted: str,
    message_text: str,
    result: 'ProcessingResult',
    tags: list,
    is_voice: bool = False,
    voice_metadata: Optional[dict] = None
) -> str:
    """
    Форматирование нового дневного файла с обработанной заметкой
    
    Returns:
        Полное содержимое нового файла
    """
    tags_str = ", ".join(tags)
    
    voice_emoji = " 🎤" if is_voice else ""
    
    tasks_section = ""
    if result.action_items:
        tasks_str = "\n".join(f"- [ ] {task}" for task in result.action_items)
        tasks_section = f"\n\n### Задачи\n\n{tasks_str}"
    
    source_info = "Telegram"
    if is_voice and voice_metadata:
        duration = voice_metadata.get("duration", 0)
        language = voice_metadata.get("language", "unknown")
        source_info = f"Telegram Voice Message • Длительность: {duration}с • Язык: {language}"
    
    content = f"""---
date: {date_formatted}
tags: [{tags_str}]
processed: true
processing_model: {result.model_used}
---

# Заметки за {date_display}

## {time_formatted}{voice_emoji}

**Summary:** {result.summary}

### Содержание

{message_text}{tasks_section}

---
*Источник: {source_info} | Обработано: Smart Processing ({result.model_used})*
"""
    
    return content
```

#### Аналогичные изменения в create_voice_note()

```python
def create_voice_note(
    self,
    transcribed_text: str,
    duration: int,
    language: str = "ru",
    processed: bool = False,
    processing_result: Optional['ProcessingResult'] = None
) -> tuple[bool, str]:
    """
    Создание голосовой заметки с поддержкой Smart Processing
    
    Args:
        transcribed_text: Транскрибированный текст
        duration: Длительность в секундах
        language: Язык сообщения
        processed: Флаг обработки через LLM
        processing_result: Результат обработки
        
    Returns:
        tuple: (успех, сообщение)
    """
    # Аналогичная логика с is_voice=True
    pass
```

---

### 5. Обновление config.py

```python
# ДОБАВИТЬ в конец файла

# Smart Processing настройки
SMART_PROCESSING_ENABLED = os.getenv('SMART_PROCESSING_ENABLED', 'true').lower() == 'true'
SMART_PROCESSING_MODEL = os.getenv('SMART_PROCESSING_MODEL', 'gpt-4o-mini')
SMART_PROCESSING_TEMPERATURE = float(os.getenv('SMART_PROCESSING_TEMPERATURE', '0.3'))
SMART_PROCESSING_MAX_TOKENS = int(os.getenv('SMART_PROCESSING_MAX_TOKENS', '500'))

# Rate limiting для LLM
MAX_LLM_REQUESTS_PER_HOUR = int(os.getenv('MAX_LLM_REQUESTS_PER_HOUR', '20'))

# Валидация Smart Processing настроек
if SMART_PROCESSING_ENABLED:
    if not OPENAI_API_KEY:
        print("⚠️ SMART_PROCESSING_ENABLED=true, но OPENAI_API_KEY не установлен")
        print("   Smart Processing будет отключен")
        SMART_PROCESSING_ENABLED = False
    
    if SMART_PROCESSING_TEMPERATURE < 0 or SMART_PROCESSING_TEMPERATURE > 2:
        print(f"⚠️ SMART_PROCESSING_TEMPERATURE={SMART_PROCESSING_TEMPERATURE} вне диапазона [0, 2]")
        print("   Используется значение по умолчанию: 0.3")
        SMART_PROCESSING_TEMPERATURE = 0.3
```

---

## 🧪 Тесты и проверка

### Минимальный набор тестов

Создать файл `test_smart_processing.py`:

```python
"""
Тесты для Smart Processing
Запуск: python -m pytest test_smart_processing.py -v
"""

import pytest
import asyncio
from llm_processor import process_text, ProcessingResult, validate_text_for_processing

@pytest.mark.asyncio
async def test_process_text_simple():
    """Тест простой обработки текста"""
    result = await process_text("Завтра купить молоко", "ru")
    
    assert result.success
    assert len(result.summary) > 0
    assert len(result.summary) <= 200
    assert len(result.tags) >= 1
    assert len(result.tags) <= 5
    # Должна быть задача "Купить молоко"
    assert any("молоко" in task.lower() for task in result.action_items)


@pytest.mark.asyncio
async def test_process_text_no_tasks():
    """Тест текста без задач"""
    result = await process_text("Хорошая погода сегодня", "ru")
    
    assert result.success
    assert len(result.action_items) == 0  # Нет задач


def test_validate_text():
    """Тест валидации текста"""
    # Валидный текст
    is_valid, msg = validate_text_for_processing("Hello world")
    assert is_valid
    
    # Пустой текст
    is_valid, msg = validate_text_for_processing("")
    assert not is_valid
    
    # Слишком длинный текст
    long_text = "a" * 11000
    is_valid, msg = validate_text_for_processing(long_text)
    assert not is_valid


@pytest.mark.asyncio
async def test_processing_result_serialization():
    """Тест сериализации ProcessingResult"""
    result = ProcessingResult(
        summary="Test summary",
        tags=["test", "example"],
        action_items=["Do something"],
        success=True
    )
    
    data = result.to_dict()
    
    assert data["summary"] == "Test summary"
    assert data["tags"] == ["test", "example"]
    assert data["success"] is True
```

### Команды для проверки

```bash
# 1. Установка зависимостей для тестов
pip install pytest pytest-asyncio

# 2. Запуск тестов
python -m pytest test_smart_processing.py -v

# 3. Проверка импортов
python -c "from llm_processor import process_text; print('✅ llm_processor OK')"
python -c "from interactive_handler import InteractiveHandler; print('✅ interactive_handler OK')"

# 4. Запуск бота
python bot.py
```

---

## ✅ Acceptance Criteria

### Критерии приемки для каждого модуля

#### llm_processor.py
- ✅ process_text() возвращает ProcessingResult
- ✅ Retry логика работает (3 попытки с exponential backoff)
- ✅ Валидация входных данных (пустой текст, слишком длинный)
- ✅ Валидация ответа LLM (required keys, типы данных)
- ✅ Теги в kebab-case, lowercase, максимум 5
- ✅ Резюме максимум 200 символов
- ✅ Обработка ошибок JSON парсинга

#### interactive_handler.py
- ✅ show_processing_preview() отправляет сообщение с inline buttons
- ✅ Callback queries обрабатываются корректно
- ✅ Режим редактирования работает (теги, резюме, задачи)
- ✅ Сессии истекают через 10 минут
- ✅ Перегенерация через LLM работает
- ✅ Сохранение без обработки работает

#### bot.py
- ✅ Smart Processing вызывается при SMART_PROCESSING_ENABLED=true
- ✅ Rate limiting работает (20 запросов в час)
- ✅ Fallback при ошибках LLM
- ✅ Callback queries регистрируются
- ✅ Голосовые сообщения обрабатываются

#### github_handler.py
- ✅ create_note() с processed=true форматирует заметку правильно
- ✅ Frontmatter содержит processed: true и processing_model
- ✅ Теги включают извлеченные + базовые (inbox, telegram)
- ✅ Секции Summary, Содержание, Задачи присутствуют
- ✅ Обратная совместимость (processed=false работает как раньше)

---

## 📝 Порядок выполнения (последовательность)

### Фаза 1: Базовая функциональность (начать здесь)

1. **config.py**
   - Добавить новые переменные окружения
   - Добавить валидацию
   - Проверка: `python -c "import config; print(config.SMART_PROCESSING_ENABLED)"`

2. **llm_processor.py** ⭐ КРИТИЧЕСКИЙ ПУТЬ
   - Создать dataclass ProcessingResult
   - Реализовать константы (SYSTEM_PROMPT)
   - Реализовать _create_user_prompt()
   - Реализовать _parse_llm_response()
   - Реализовать _validate_response()
   - Реализовать validate_text_for_processing()
   - Реализовать _call_llm_with_retry()
   - Реализовать process_text() (главная функция)
   - Проверка: запустить test_smart_processing.py

### Фаза 2: Интерактивность

3. **interactive_handler.py** ⭐ КРИТИЧЕСКИЙ ПУТЬ
   - Создать dataclass ProcessingSession
   - Создать класс InteractiveHandler
   - Реализовать _generate_preview_text()
   - Реализовать _create_inline_keyboard()
   - Реализовать show_processing_preview()
   - Реализовать handle_callback()
   - Реализовать _handle_approve()
   - Реализовать _handle_edit_tags(), _handle_edit_summary(), _handle_edit_tasks()
   - Реализовать _handle_regenerate()
   - Реализовать _handle_save_raw()
   - Реализовать handle_edit_response()
   - Проверка: запустить бота, отправить тестовое сообщение

### Фаза 3: Интеграция

4. **github_handler.py**
   - Добавить импорт ProcessingResult (Optional type hint)
   - Реализовать _format_processed_note()
   - Реализовать _format_new_daily_file_processed()
   - Обновить create_note() (добавить параметры processed, processing_result)
   - Обновить create_voice_note() (аналогично)
   - Проверка: вызвать с processed=True и проверить формат в GitHub

5. **bot.py**
   - Добавить импорты (llm_processor, interactive_handler)
   - Создать interactive_handler = InteractiveHandler(bot)
   - Создать llm_requests dict
   - Реализовать check_llm_rate_limit()
   - Обновить handle_text_message() (добавить Smart Processing блок)
   - Обновить handle_voice_message() (аналогично)
   - Добавить обработчик @dp.callback_query()
   - Проверка: запустить бота, полный E2E тест

### Фаза 4: Тестирование и документация

6. **Тестирование**
   - Запустить все 7 тестовых сценариев из ТЗ
   - Проверить rate limiting
   - Проверить fallback при ошибках
   - Проверить формат файлов в Obsidian

7. **Документация**
   - Уже создана: SMART_PROCESSING.md
   - Уже создана: SMART_PROCESSING_TZ.md
   - Обновить README.md (добавить секцию о Smart Processing)

---

## 🚨 Важные замечания для AI-агента

### Критические моменты

1. **Async/await**
   - Все LLM вызовы должны быть async
   - asyncio.sleep() для задержек, НЕ time.sleep()
   - Правильные await для всех async функций

2. **Error handling**
   - Обязательно try/except для OpenAI API
   - Логирование всех ошибок
   - Graceful fallback при ошибках

3. **Type hints**
   - Использовать Optional['ProcessingResult'] для forward references
   - Импортировать List, Dict, Optional из typing

4. **Markdown formatting**
   - Использовать triple backticks для кода в превью
   - parse_mode="Markdown" в message.answer()
   - Экранировать специальные символы если нужно

5. **Callback data**
   - Максимум 64 байта для callback_data
   - Простые строки: "approve", "edit_tags", etc.

6. **Session management**
   - Очистка expired sessions
   - Удаление sessions после сохранения
   - Проверка наличия session перед использованием

### Частые ошибки (избегать)

❌ `from llm_processor import ProcessingResult` в github_handler.py - вызывает circular import  
✅ Использовать type hint: `Optional['ProcessingResult']`

❌ `time.sleep()` в async функциях  
✅ `await asyncio.sleep()`

❌ Забыть await перед async функциями  
✅ Всегда `await process_text()`, `await handler.show_processing_preview()`

❌ Не проверять наличие session в callback handler  
✅ Всегда проверять `if not session: return`

❌ Не удалять session после сохранения  
✅ `del self.sessions[user_id]` после успешного сохранения

---

## 🎯 Готовность к началу

Перед началом реализации убедитесь:

- ✅ Прочитан [SMART_PROCESSING_TZ.md](./SMART_PROCESSING_TZ.md)
- ✅ Прочитан этот файл (SMART_PROCESSING_IMPLEMENTATION.md)
- ✅ Понятна архитектура и зависимости между модулями
- ✅ Готовы точные сигнатуры функций
- ✅ Есть тестовые сценарии для проверки
- ✅ Понятен порядок выполнения (Фазы 1-4)

**Начинать с Фазы 1, пункт 1: config.py**

---

*Удачи в реализации! 🚀*
