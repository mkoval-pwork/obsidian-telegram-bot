"""
Утилиты для обработки заметок
"""
from datetime import datetime
from typing import Optional


def extract_priority(text: str) -> Optional[str]:
    """
    Извлечение приоритета из текста
    
    Args:
        text: Текст для анализа
        
    Returns:
        "high", "medium", "low" или None
        
    Example:
        >>> extract_priority("Срочно! Купить молоко")
        'high'
        >>> extract_priority("Нужно позвонить")
        None
    """
    text_lower = text.lower()
    
    # ВАЖНО: Низкий приоритет проверяем ПЕРВЫМ, чтобы "не срочно" не попало в "срочно"
    # Низкий приоритет
    low_keywords = [
        'когда-нибудь', 'не спешно', 'не срочно',
        'можно позже', 'при случае', 'если будет время'
    ]
    if any(keyword in text_lower for keyword in low_keywords):
        return "low"
    
    # Высокий приоритет
    high_keywords = [
        'срочно', 'asap', 'важно', 'критично', 
        'немедленно', 'обязательно', 'приоритет',
        'горит', 'пожар'
    ]
    if any(keyword in text_lower for keyword in high_keywords):
        return "high"
    
    # По умолчанию средний приоритет не возвращаем (будет установлен в ActionItem)
    return None


def normalize_date_for_obsidian(date_str: str, reference_date: Optional[datetime] = None) -> str:
    """
    Нормализация даты для использования в Obsidian
    
    Args:
        date_str: Дата в ISO формате (YYYY-MM-DD)
        reference_date: Референсная дата (по умолчанию текущая)
        
    Returns:
        "today", "tomorrow" или ISO формат
        
    Example:
        >>> normalize_date_for_obsidian("2026-02-17")
        'today'  # если сегодня 2026-02-17
    """
    if not reference_date:
        reference_date = datetime.now()
    
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        ref_date = reference_date.date()
        
        delta = (target_date - ref_date).days
        
        if delta == 0:
            return "today"
        elif delta == 1:
            return "tomorrow"
        else:
            return date_str
    except ValueError:
        return date_str
