#!/bin/bash

# Скрипт для запуска бота

# Проверка наличия виртуального окружения
if [ ! -d "venv" ]; then
    echo "Создание виртуального окружения..."
    python3 -m venv venv
fi

# Активация виртуального окружения
source venv/bin/activate

# Установка зависимостей
echo "Установка зависимостей..."
pip install -r requirements.txt

# Проверка наличия .env файла
if [ ! -f ".env" ]; then
    echo "ОШИБКА: Файл .env не найден!"
    echo "Создайте файл .env и заполните необходимые переменные."
    exit 1
fi

# Запуск бота
echo "Запуск бота..."
python bot.py
