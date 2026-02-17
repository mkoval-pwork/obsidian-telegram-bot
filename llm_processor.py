"""
Модуль для обработки текста через OpenAI LLM (GPT-4o-mini)
"""
import json
import logging
import asyncio
import time
from dataclasses import dataclass
from typing import Optional, List
from openai import OpenAI, OpenAIError

import config

# Настройка логирования
logger = logging.getLogger(__name__)

# Константы
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
