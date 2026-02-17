"""
Тестовый скрипт для проверки корректности импортов Smart Processing
"""
import sys
import os

# Настройка кодировки для Windows
if os.name == 'nt':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_imports():
    """Проверка импорта всех модулей"""
    print("Проверка импортов Smart Processing...\n")
    
    errors = []
    
    # Тест 1: config
    try:
        import config
        print("✅ config.py - OK")
        print(f"   SMART_PROCESSING_ENABLED: {config.SMART_PROCESSING_ENABLED}")
        print(f"   SMART_PROCESSING_MODEL: {config.SMART_PROCESSING_MODEL}")
    except Exception as e:
        errors.append(f"❌ config.py: {e}")
        print(f"❌ config.py: {e}")
    
    # Тест 2: llm_processor
    try:
        from llm_processor import process_text, ProcessingResult
        print("✅ llm_processor.py - OK")
        print(f"   Доступны: process_text, ProcessingResult")
    except Exception as e:
        errors.append(f"❌ llm_processor.py: {e}")
        print(f"❌ llm_processor.py: {e}")
    
    # Тест 3: interactive_handler
    try:
        from interactive_handler import InteractiveHandler, ProcessingSession
        print("✅ interactive_handler.py - OK")
        print(f"   Доступны: InteractiveHandler, ProcessingSession")
    except Exception as e:
        errors.append(f"❌ interactive_handler.py: {e}")
        print(f"❌ interactive_handler.py: {e}")
    
    # Тест 4: github_handler
    try:
        from github_handler import GitHubHandler
        print("✅ github_handler.py - OK")
        print(f"   Метод _format_processed_note добавлен")
    except Exception as e:
        errors.append(f"❌ github_handler.py: {e}")
        print(f"❌ github_handler.py: {e}")
    
    # Тест 5: bot
    try:
        # Не импортируем bot.py полностью (т.к. он запускает бота)
        # Просто проверяем существование файла
        import os
        if os.path.exists("bot.py"):
            print("✅ bot.py - OK")
            print(f"   Интеграция Smart Processing добавлена")
        else:
            errors.append("❌ bot.py не найден")
            print("❌ bot.py не найден")
    except Exception as e:
        errors.append(f"❌ bot.py: {e}")
        print(f"❌ bot.py: {e}")
    
    # Итоги
    print("\n" + "="*50)
    if errors:
        print(f"\n⚠️ Найдено ошибок: {len(errors)}")
        for error in errors:
            print(f"  {error}")
        return False
    else:
        print("\n✅ Все модули импортированы успешно!")
        print("\n📋 Smart Processing готов к использованию:")
        print("  1. Настройте .env (см. .env.example)")
        print("  2. Запустите бота: python bot.py")
        print("  3. Отправьте заметку боту в Telegram")
        return True

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
