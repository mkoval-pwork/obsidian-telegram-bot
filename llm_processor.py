"""
Модуль для обработки текста через OpenAI LLM (GPT-4o-mini)
"""
import json
import logging
import asyncio
import time
from dataclasses import dataclass, asdict
from typing import Optional, List
from datetime import datetime
from openai import OpenAI, OpenAIError

import config
from date_parser import DateParser, extract_priority, normalize_date_for_obsidian

# Настройка логирования
logger = logging.getLogger(__name__)

# Константы
MAX_RETRIES = 3
BASE_WAIT_TIME = 2  # секунды для экспоненциальной задержки
MAX_TEXT_LENGTH = 10000  # максимальная длина текста для обработки

SYSTEM_PROMPT = """Ты - ассистент для обработки заметок в системе Personal Knowledge Management (Obsidian).
Твоя задача - проанализировать текст и извлечь структурированную информацию с ВРЕМЕННЫМ КОНТЕКСТОМ.

ВАЖНЫЕ ПРАВИЛА:
1. Извлекай только то, что явно присутствует в тексте
2. НЕ добавляй информацию от себя
3. СОХРАНЯЙ все упоминания дат и времени
4. Теги должны быть релевантны содержанию
5. Резюме должно быть информативным, но кратким
6. Задачи - только конкретные действия, которые упомянуты в тексте

ИЗВЛЕКАЙ:
1. ТЕГИ (tags): 
   - Для коротких сообщений (<30 слов): 2-3 тега
   - Для длинных сообщений: 3-5 тегов
   - Английский язык, lowercase
   - Формат: kebab-case (через дефис)
   - От общих к конкретным
   - Примеры: task, shopping, meeting, health, family, urgent

2. РЕЗЮМЕ (summary):
   - Краткое описание (1-2 предложения)
   - Максимум 200 символов
   - На том же языке, что и текст
   - Фокус на ключевых идеях

3. ЗАДАЧИ (action_items):
   - Список объектов с полями: text, date, time, priority, tags
   - text: конкретное действие (глагол + объект)
   - date: дата в формате "YYYY-MM-DD" или null (НЕ используй "today", "tomorrow")
   - time: время в формате "HH:MM" или null
   - priority: "high", "medium", "low" или null
   - tags: массив 1-2 релевантных тегов для задачи
   - Если задач нет - пустой массив

ОПРЕДЕЛЕНИЕ ПРИОРИТЕТА:
- high: "срочно", "важно", "ASAP", "критично", "обязательно"
- medium: обычные задачи без явных маркеров
- low: "когда-нибудь", "не спешно", "при случае"

ИЗВЛЕЧЕНИЕ ДАТ:
- "сегодня" → используй переданную reference_date
- "завтра" → reference_date + 1 день
- "послезавтра" → reference_date + 2 дня
- "через N дней" → reference_date + N дней
- "в понедельник", "во вторник" → найди следующий такой день
- "на следующей неделе" → reference_date + 7 дней
- "DD.MM.YYYY" или "DD.MM" → конвертируй в YYYY-MM-DD

ФОРМАТ ОТВЕТА (строго JSON):
{
  "summary": "Краткое описание содержания",
  "tags": ["tag1", "tag2"],
  "action_items": [
    {
      "text": "Купить молоко",
      "date": "2026-02-18",
      "time": "10:00",
      "priority": "medium",
      "tags": ["shopping"]
    }
  ]
}

ПРИМЕРЫ:

Пример 1 (короткая заметка):
Вход: "Сходить на массаж в 19:00"
Ответ:
{
  "summary": "Запись на массаж вечером",
  "tags": ["health", "self-care"],
  "action_items": [
    {
      "text": "Сходить на массаж",
      "date": null,
      "time": "19:00",
      "priority": "medium",
      "tags": ["health"]
    }
  ]
}

Пример 2 (с датами):
Вход: "Завтра в 10:00 купить молоко. Сегодня вечером позвонить маме."
reference_date: "2026-02-17"
Ответ:
{
  "summary": "Список задач: покупки и семья на ближайшие дни",
  "tags": ["task", "shopping", "family"],
  "action_items": [
    {
      "text": "Купить молоко",
      "date": "2026-02-18",
      "time": "10:00",
      "priority": "medium",
      "tags": ["shopping"]
    },
    {
      "text": "Позвонить маме",
      "date": "2026-02-17",
      "time": "19:00",
      "priority": "medium",
      "tags": ["family"]
    }
  ]
}

Пример 3 (приоритеты):
Вход: "СРОЧНО! Отправить отчет до конца дня"
Ответ:
{
  "summary": "Срочная задача: отправить отчет сегодня",
  "tags": ["urgent", "work", "task"],
  "action_items": [
    {
      "text": "Отправить отчет",
      "date": "2026-02-17",
      "time": null,
      "priority": "high",
      "tags": ["work", "urgent"]
    }
  ]
}

НЕ добавляй никакого текста кроме JSON!"""


@dataclass
class ActionItem:
    """Структурированная задача с временным контекстом"""
    text: str  # Текст задачи
    date: Optional[str] = None  # Дата в формате YYYY-MM-DD или "today", "tomorrow"
    time: Optional[str] = None  # Время в формате HH:MM
    priority: Optional[str] = None  # "high", "medium", "low"
    tags: List[str] = None  # Список тегов для задачи
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> dict:
        """Сериализация в dict"""
        return asdict(self)
    
    def to_markdown(self) -> str:
        """
        Форматирование задачи в Markdown (для Obsidian Tasks плагина)
        
        Returns:
            Строка формата: "- [ ] Task 📅 date ⏰ time #tag1 #tag2"
        """
        result = f"- [ ] {self.text}"
        
        if self.date:
            result += f" 📅 {self.date}"
        
        if self.time:
            result += f" ⏰ {self.time}"
        
        if self.tags:
            tags_str = " ".join(f"#{tag}" for tag in self.tags)
            result += f" {tags_str}"
        
        return result


@dataclass
class ProcessingResult:
    """Результат обработки текста через LLM"""
    summary: str
    tags: List[str]
    action_items: List[ActionItem]  # Изменено: теперь список ActionItem вместо строк
    success: bool
    error_message: Optional[str] = None
    processing_time: float = 0.0
    model_used: str = "gpt-4o-mini"
    dates_mentioned: List[str] = None  # Новое: все упомянутые даты
    processing_version: str = "2.0"  # Новое: версия обработки
    
    def __post_init__(self):
        if self.dates_mentioned is None:
            self.dates_mentioned = []
    
    def to_dict(self) -> dict:
        """Сериализация в dict"""
        return {
            "summary": self.summary,
            "tags": self.tags,
            "action_items": [item.to_dict() for item in self.action_items],
            "success": self.success,
            "error_message": self.error_message,
            "processing_time": self.processing_time,
            "model_used": self.model_used,
            "dates_mentioned": self.dates_mentioned,
            "processing_version": self.processing_version
        }


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
        reference_date = datetime.now()
        response_data = await _call_llm_with_retry(client, text, language, reference_date)
        
        # Парсинг и валидация ответа
        if not _validate_response(response_data):
            return ProcessingResult(
                summary="",
                tags=[],
                action_items=[],
                success=False,
                error_message="LLM вернул некорректные данные"
            )
        
        # Конвертация action_items из dict в ActionItem объекты
        action_items = []
        dates_mentioned = []
        
        for item_data in response_data.get("action_items", []):
            # Парсинг и нормализация даты
            date = item_data.get("date")
            if date:
                dates_mentioned.append(date)
                # Нормализация для Obsidian (today/tomorrow)
                date = normalize_date_for_obsidian(date, reference_date)
            
            action_item = ActionItem(
                text=item_data.get("text", ""),
                date=date,
                time=item_data.get("time"),
                priority=item_data.get("priority"),
                tags=item_data.get("tags", [])
            )
            action_items.append(action_item)
        
        processing_time = time.time() - start_time
        
        return ProcessingResult(
            summary=response_data.get("summary", ""),
            tags=response_data.get("tags", []),
            action_items=action_items,
            success=True,
            processing_time=processing_time,
            model_used=config.SMART_PROCESSING_MODEL,
            dates_mentioned=sorted(list(set(dates_mentioned))),
            processing_version="2.0"
        )
        
    except Exception as e:
        logger.error(f"Unexpected error in process_text: {e}", exc_info=True)
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
    language: str,
    reference_date: Optional[datetime] = None
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
            user_prompt = _create_user_prompt(text, language, reference_date)
            
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
            
            logger.info(
                f"LLM processing successful on attempt {attempt + 1}",
                extra={"text_length": len(text), "model": config.SMART_PROCESSING_MODEL}
            )
            
            return response_data
            
        except OpenAIError as e:
            last_error = e
            logger.warning(f"OpenAI API error on attempt {attempt + 1}/{MAX_RETRIES}: {e}")
            
            if attempt < MAX_RETRIES - 1:
                wait_time = BASE_WAIT_TIME ** attempt
                logger.info(f"Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
        
        except Exception as e:
            last_error = e
            logger.error(f"Unexpected error on attempt {attempt + 1}/{MAX_RETRIES}: {e}")
            
            if attempt < MAX_RETRIES - 1:
                wait_time = BASE_WAIT_TIME ** attempt
                await asyncio.sleep(wait_time)
    
    # Все попытки исчерпаны
    error_msg = f"LLM processing failed after {MAX_RETRIES} attempts: {str(last_error)}"
    logger.error(error_msg)
    raise Exception(error_msg)


def _create_user_prompt(text: str, language: str, reference_date: Optional[datetime] = None) -> str:
    """
    Создание user prompt для LLM
    
    Args:
        text: Текст заметки
        language: Код языка (ru, en, uk, etc.)
        reference_date: Референсная дата для расчета относительных дат
        
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
    
    if not reference_date:
        reference_date = datetime.now()
    
    ref_date_str = reference_date.strftime("%Y-%m-%d")
    
    return f"""Проанализируй следующий текст и извлеки структурированную информацию:

ТЕКСТ:
{text}

КОНТЕКСТ:
- reference_date: {ref_date_str} (используй для расчета "сегодня", "завтра", etc.)
- Язык резюме: {lang_name}
- Теги: английский, lowercase, kebab-case
- Задачи: извлекай text, date, time, priority, tags

ВАЖНО:
- Сохраняй временной контекст из текста
- Конвертируй относительные даты ("завтра", "через 2 дня") в YYYY-MM-DD формат
- Извлекай время в формате HH:MM

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
    
    # Валидация action_items (должны быть dict с полем text)
    valid_action_items = []
    for item in response_data["action_items"]:
        if isinstance(item, dict) and "text" in item:
            # Валидация полей ActionItem
            validated_item = {
                "text": str(item.get("text", "")),
                "date": item.get("date") if item.get("date") else None,
                "time": item.get("time") if item.get("time") else None,
                "priority": item.get("priority") if item.get("priority") in ["high", "medium", "low"] else None,
                "tags": [tag.lower().replace(" ", "-") for tag in item.get("tags", []) if isinstance(tag, str)][:2]
            }
            valid_action_items.append(validated_item)
    
    response_data["action_items"] = valid_action_items
    
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
