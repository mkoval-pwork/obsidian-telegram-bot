"""
Unit тесты для utils.py
"""
import unittest
from datetime import datetime
from utils import extract_priority, normalize_date_for_obsidian


class TestExtractPriority(unittest.TestCase):
    """Тесты для функции extract_priority"""
    
    def test_high_priority_keywords(self):
        """Тест определения высокого приоритета"""
        test_cases = [
            "Срочно! Купить молоко",
            "ASAP нужно отправить отчет",
            "Важно: позвонить клиенту",
            "Критично выполнить задачу",
            "Немедленно исправить баг",
            "Обязательно подготовить презентацию",
            "Приоритет: разобраться с проблемой",
            "Горит задача",
            "Пожар на проекте"
        ]
        
        for text in test_cases:
            with self.subTest(text=text):
                result = extract_priority(text)
                self.assertEqual(result, "high", f"Ожидался high для: {text}")
    
    def test_low_priority_keywords(self):
        """Тест определения низкого приоритета"""
        test_cases = [
            "Когда-нибудь нужно почистить код",
            "Не спешно разобраться с документацией",
            "Не срочно, но хотелось бы сделать",
            "Можно позже посмотреть",
            "При случае проверить",
            "Если будет время, исправить"
        ]
        
        for text in test_cases:
            with self.subTest(text=text):
                result = extract_priority(text)
                self.assertEqual(result, "low", f"Ожидался low для: {text}")
    
    def test_no_priority_keywords(self):
        """Тест когда нет явных маркеров приоритета"""
        test_cases = [
            "Купить молоко",
            "Позвонить маме",
            "Подготовить отчет",
            "Встреча с клиентом"
        ]
        
        for text in test_cases:
            with self.subTest(text=text):
                result = extract_priority(text)
                self.assertIsNone(result, f"Ожидался None для: {text}")
    
    def test_low_priority_before_high(self):
        """Тест что 'не срочно' определяется как low, а не high"""
        text = "Не срочно сделать задачу"
        result = extract_priority(text)
        self.assertEqual(result, "low", "Должен быть low, не high")
    
    def test_case_insensitive(self):
        """Тест регистронезависимости"""
        test_cases = [
            ("СРОЧНО", "high"),
            ("Срочно", "high"),
            ("срочно", "high"),
            ("КОГДА-НИБУДЬ", "low"),
            ("Когда-Нибудь", "low")
        ]
        
        for text, expected in test_cases:
            with self.subTest(text=text):
                result = extract_priority(text)
                self.assertEqual(result, expected)


class TestNormalizeDateForObsidian(unittest.TestCase):
    """Тесты для функции normalize_date_for_obsidian"""
    
    def test_today(self):
        """Тест конвертации сегодняшней даты в 'today'"""
        ref_date = datetime(2026, 2, 17, 15, 30)
        date_str = "2026-02-17"
        
        result = normalize_date_for_obsidian(date_str, ref_date)
        self.assertEqual(result, "today")
    
    def test_tomorrow(self):
        """Тест конвертации завтрашней даты в 'tomorrow'"""
        ref_date = datetime(2026, 2, 17, 15, 30)
        date_str = "2026-02-18"
        
        result = normalize_date_for_obsidian(date_str, ref_date)
        self.assertEqual(result, "tomorrow")
    
    def test_past_date(self):
        """Тест что прошедшие даты остаются в ISO формате"""
        ref_date = datetime(2026, 2, 17, 15, 30)
        date_str = "2026-02-15"
        
        result = normalize_date_for_obsidian(date_str, ref_date)
        self.assertEqual(result, "2026-02-15")
    
    def test_future_date(self):
        """Тест что будущие даты (не завтра) остаются в ISO формате"""
        ref_date = datetime(2026, 2, 17, 15, 30)
        date_str = "2026-02-20"
        
        result = normalize_date_for_obsidian(date_str, ref_date)
        self.assertEqual(result, "2026-02-20")
    
    def test_invalid_date_format(self):
        """Тест что невалидный формат возвращается без изменений"""
        ref_date = datetime(2026, 2, 17, 15, 30)
        date_str = "invalid-date"
        
        result = normalize_date_for_obsidian(date_str, ref_date)
        self.assertEqual(result, "invalid-date")
    
    def test_no_reference_date(self):
        """Тест что без reference_date используется текущая дата"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        result = normalize_date_for_obsidian(today)
        self.assertEqual(result, "today")


if __name__ == '__main__':
    unittest.main()
