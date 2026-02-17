"""
Модуль для парсинга и обработки дат и времени из текста
"""
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from dataclasses import dataclass


@dataclass
class ParsedDate:
    """Распознанная дата/время из текста"""
    original_text: str  # Оригинальный текст ("завтра", "через 2 дня")
    date: Optional[str]  # ISO формат YYYY-MM-DD или "today", "tomorrow"
    time: Optional[str]  # Формат HH:MM
    is_relative: bool  # True если дата относительная (завтра, через неделю)
    confidence: float  # Уверенность парсинга 0.0-1.0


class DateParser:
    """Парсер дат и времени из текста на русском языке"""
    
    # Паттерны для времени
    TIME_PATTERNS = [
        r'в\s+(\d{1,2}):(\d{2})',  # "в 10:00", "в 9:30"
        r'в\s+(\d{1,2})\s+час',  # "в 10 часов"
        r'(\d{1,2}):(\d{2})',  # "10:00", "9:30"
    ]
    
    # Относительные даты (от более длинных к коротким для правильного матчинга)
    RELATIVE_DATES = {
        'послезавтра': 2,
        'позавчера': -2,
        'сегодня': 0,
        'завтра': 1,
        'вчера': -1,
    }
    
    # Дни недели
    WEEKDAYS = {
        'понедельник': 0,
        'вторник': 1,
        'среда': 2,
        'четверг': 3,
        'пятница': 4,
        'суббота': 5,
        'воскресенье': 6,
    }
    
    # Периоды
    PERIODS = {
        'утром': '09:00',
        'днем': '14:00',
        'вечером': '19:00',
        'ночью': '23:00',
    }
    
    def __init__(self, reference_date: Optional[datetime] = None):
        """
        Args:
            reference_date: Референсная дата для расчета относительных дат
                          (по умолчанию текущая дата)
        """
        self.reference_date = reference_date or datetime.now()
    
    def parse(self, text: str) -> List[ParsedDate]:
        """
        Парсинг всех дат и времен из текста
        
        Args:
            text: Текст для анализа
            
        Returns:
            Список найденных дат/времен
            
        Example:
            >>> parser = DateParser()
            >>> results = parser.parse("Завтра в 10:00 купить молоко")
            >>> results[0].date
            '2026-02-18'
            >>> results[0].time
            '10:00'
        """
        text_lower = text.lower()
        parsed_dates = []
        
        # Поиск относительных дат (сегодня, завтра, послезавтра)
        for relative_word, days_offset in self.RELATIVE_DATES.items():
            if relative_word in text_lower:
                date = self._calculate_date(days_offset)
                time = self._extract_time_near_word(text_lower, relative_word)
                
                parsed_dates.append(ParsedDate(
                    original_text=relative_word,
                    date=date.strftime('%Y-%m-%d'),
                    time=time,
                    is_relative=True,
                    confidence=0.95
                ))
        
        # Поиск дней недели ("в понедельник", "во вторник", "в пятницу")
        for weekday, weekday_num in self.WEEKDAYS.items():
            # Паттерн: "в/во + день недели" или просто "день недели" в начале предложения
            pattern = rf'\b(?:в|во)\s+{weekday}\b|\b{weekday}\b'
            match = re.search(pattern, text_lower)
            if match:
                # Проверяем, что это не часть другого слова (например, "понедельника")
                if match.group().startswith('в') or match.group().startswith('во'):
                    date = self._find_next_weekday(weekday_num)
                    time = self._extract_time_near_word(text_lower, weekday)
                    
                    parsed_dates.append(ParsedDate(
                        original_text=weekday,
                        date=date.strftime('%Y-%m-%d'),
                        time=time,
                        is_relative=True,
                        confidence=0.85
                    ))
                    break  # Найден день недели, переходим к следующей итерации
        
        # Поиск "через N дней/недель"
        through_pattern = r'через\s+(\d+)\s+(день|дня|дней|неделю|недели|недель)'
        matches = re.finditer(through_pattern, text_lower)
        for match in matches:
            count = int(match.group(1))
            unit = match.group(2)
            
            if unit in ['день', 'дня', 'дней']:
                date = self._calculate_date(count)
            else:  # недели
                date = self._calculate_date(count * 7)
            
            time = self._extract_time_near_position(text_lower, match.start())
            
            parsed_dates.append(ParsedDate(
                original_text=match.group(0),
                date=date.strftime('%Y-%m-%d'),
                time=time,
                is_relative=True,
                confidence=0.90
            ))
        
        # Поиск "на следующей неделе"
        if 'на следующей неделе' in text_lower or 'на будущей неделе' in text_lower:
            date = self._calculate_date(7)
            time = self._extract_time_from_text(text_lower)
            
            parsed_dates.append(ParsedDate(
                original_text='на следующей неделе',
                date=date.strftime('%Y-%m-%d'),
                time=time,
                is_relative=True,
                confidence=0.80
            ))
        
        # Поиск абсолютных дат (DD.MM, DD.MM.YYYY)
        absolute_dates = self._parse_absolute_dates(text_lower)
        parsed_dates.extend(absolute_dates)
        
        # Поиск периодов дня (утром, вечером)
        for period, default_time in self.PERIODS.items():
            if period in text_lower:
                # Проверяем, есть ли уже дата для этого периода
                existing_time = any(pd.time for pd in parsed_dates)
                if not existing_time:
                    # Ищем ближайшую дату
                    closest_date = parsed_dates[0] if parsed_dates else None
                    if closest_date and not closest_date.time:
                        closest_date.time = default_time
        
        # Удаление дубликатов (приоритет более специфичным)
        parsed_dates = self._deduplicate_dates(parsed_dates)
        
        return parsed_dates
    
    def _calculate_date(self, days_offset: int) -> datetime:
        """Расчет даты относительно reference_date"""
        return self.reference_date + timedelta(days=days_offset)
    
    def _find_next_weekday(self, target_weekday: int) -> datetime:
        """
        Поиск следующего дня недели
        
        Args:
            target_weekday: Номер дня недели (0=понедельник, 6=воскресенье)
            
        Returns:
            Дата следующего такого дня недели
        """
        current_weekday = self.reference_date.weekday()
        days_ahead = target_weekday - current_weekday
        
        if days_ahead <= 0:  # Целевой день уже прошел на этой неделе
            days_ahead += 7
        
        return self.reference_date + timedelta(days=days_ahead)
    
    def _extract_time_from_text(self, text: str) -> Optional[str]:
        """Извлечение времени из текста"""
        for pattern in self.TIME_PATTERNS:
            match = re.search(pattern, text)
            if match:
                if len(match.groups()) == 2:
                    hour, minute = match.groups()
                    return f"{int(hour):02d}:{int(minute):02d}"
                else:
                    hour = match.group(1)
                    return f"{int(hour):02d}:00"
        return None
    
    def _extract_time_near_word(self, text: str, word: str, window: int = 50) -> Optional[str]:
        """
        Извлечение времени рядом с указанным словом
        
        Args:
            text: Текст для поиска
            word: Слово, около которого искать время
            window: Окно поиска в символах
        """
        pos = text.find(word)
        if pos == -1:
            return self._extract_time_from_text(text)
        
        start = max(0, pos - window)
        end = min(len(text), pos + len(word) + window)
        snippet = text[start:end]
        
        return self._extract_time_from_text(snippet) or self._extract_time_from_text(text)
    
    def _extract_time_near_position(self, text: str, position: int, window: int = 50) -> Optional[str]:
        """Извлечение времени рядом с указанной позицией"""
        start = max(0, position - window)
        end = min(len(text), position + window)
        snippet = text[start:end]
        
        return self._extract_time_from_text(snippet) or self._extract_time_from_text(text)
    
    def _parse_absolute_dates(self, text: str) -> List[ParsedDate]:
        """
        Парсинг абсолютных дат в формате DD.MM или DD.MM.YYYY
        
        Args:
            text: Текст для поиска
            
        Returns:
            Список найденных абсолютных дат
        """
        dates = []
        
        # Паттерн DD.MM.YYYY
        pattern_full = r'\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b'
        for match in re.finditer(pattern_full, text):
            day, month, year = match.groups()
            try:
                date = datetime(int(year), int(month), int(day))
                time = self._extract_time_near_position(text, match.start())
                
                dates.append(ParsedDate(
                    original_text=match.group(0),
                    date=date.strftime('%Y-%m-%d'),
                    time=time,
                    is_relative=False,
                    confidence=1.0
                ))
            except ValueError:
                pass  # Невалидная дата
        
        # Паттерн DD.MM (текущий год)
        pattern_short = r'\b(\d{1,2})\.(\d{1,2})\b'
        for match in re.finditer(pattern_short, text):
            day, month = match.groups()
            try:
                date = datetime(self.reference_date.year, int(month), int(day))
                time = self._extract_time_near_position(text, match.start())
                
                dates.append(ParsedDate(
                    original_text=match.group(0),
                    date=date.strftime('%Y-%m-%d'),
                    time=time,
                    is_relative=False,
                    confidence=0.90
                ))
            except ValueError:
                pass  # Невалидная дата
        
        return dates
    
    def _deduplicate_dates(self, dates: List[ParsedDate]) -> List[ParsedDate]:
        """
        Удаление дубликатов дат
        
        При конфликтах приоритет имеют:
        1. Более высокий confidence
        2. Более конкретная информация (есть время)
        """
        if not dates:
            return []
        
        # Группировка по дате
        date_groups: Dict[str, List[ParsedDate]] = {}
        for pd in dates:
            if pd.date not in date_groups:
                date_groups[pd.date] = []
            date_groups[pd.date].append(pd)
        
        # Выбор лучшего варианта для каждой даты
        result = []
        for date, group in date_groups.items():
            # Сортировка: сначала с временем, потом по confidence
            best = max(group, key=lambda x: (x.time is not None, x.confidence))
            result.append(best)
        
        return sorted(result, key=lambda x: x.date)


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
