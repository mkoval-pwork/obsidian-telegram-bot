# 📖 Шпаргалка команд

Все важные команды в одном месте.

---

## 🔌 Подключение к VPS

```bash
ssh root@ваш-ip
```

---

## 🐳 Docker команды

### Управление контейнером
```bash
docker-compose up -d              # Запустить в фоне
docker-compose down               # Остановить и удалить
docker-compose start              # Запустить существующий
docker-compose stop               # Остановить
docker-compose restart            # Перезапустить
docker-compose ps                 # Статус контейнеров
```

### Логи
```bash
docker-compose logs -f obsidian-bot           # Логи в реальном времени
docker-compose logs --tail=50 obsidian-bot    # Последние 50 строк
docker-compose logs --since 1h obsidian-bot   # Логи за последний час
```

### Пересборка
```bash
docker-compose up -d --build      # Пересобрать и запустить
docker-compose build --no-cache   # Пересобрать без кеша
```

---

## 📺 Screen команды

### Создание и управление
```bash
screen -S obsidian-bot            # Создать новую сессию
screen -r obsidian-bot            # Подключиться к сессии
screen -ls                        # Список всех сессий
screen -X -S obsidian-bot quit    # Убить сессию
```

### Внутри screen
```
Ctrl+A, затем D    # Отключиться (detach)
Ctrl+A, затем K    # Убить сессию
Ctrl+C             # Остановить бот
```

### Запуск бота в фоне
```bash
screen -dmS obsidian-bot python3 bot.py
```

---

## 📁 Git команды

```bash
git pull                          # Обновить код
git status                        # Статус изменений
git log --oneline -5              # Последние 5 коммитов
git clone URL                     # Клонировать репозиторий
```

---

## 🐍 Python команды

```bash
python3 --version                 # Версия Python
pip3 list                         # Установленные пакеты
pip3 install -r requirements.txt  # Установить зависимости
pip3 install --upgrade пакет      # Обновить пакет
```

---

## 📊 Мониторинг системы

```bash
htop                              # Монитор процессов (q для выхода)
df -h                             # Использование диска
free -h                           # Использование RAM
ps aux | grep python              # Процессы Python
top                               # Монитор процессов (базовый)
```

---

## 🔍 Просмотр файлов

```bash
cat .env                          # Показать .env
nano .env                         # Редактировать .env
ls -la                            # Список файлов
pwd                               # Текущая директория
cd /root/obsidian-telegram-bot    # Перейти в папку бота
```

---

## 🔄 Обновление бота

### Docker:
```bash
cd /root/obsidian-telegram-bot
docker-compose down
git pull
docker-compose up -d --build
```

### Screen:
```bash
screen -X -S obsidian-bot quit
cd /root/obsidian-telegram-bot
git pull
pip3 install -r requirements.txt
screen -dmS obsidian-bot python3 bot.py
```

---

## 🔥 Firewall (ufw)

```bash
ufw status                        # Статус
ufw enable                        # Включить
ufw disable                       # Выключить
ufw allow 22/tcp                  # Разрешить SSH
```

---

## 🆘 Диагностика проблем

### Проверка .env
```bash
cat .env
```

### Тест подключения к GitHub
```bash
curl -H "Authorization: token ваш_github_token" https://api.github.com/user
```

### Проверка интернета
```bash
ping -c 3 google.com
curl -I https://api.telegram.org
```

### Логи системы
```bash
journalctl -xe                    # Последние ошибки системы
dmesg | tail                      # Логи ядра
```

---

## 🔒 Безопасность

### Создание пользователя
```bash
adduser botuser
usermod -aG sudo botuser
su - botuser
```

### Настройка SSH ключей
```bash
# На вашем ПК (PowerShell):
ssh-keygen -t rsa

# Копирование ключа на сервер:
ssh-copy-id root@ваш-ip
```

---

## 📱 Тестирование бота

1. Откройте Telegram
2. Найдите своего бота
3. `/start` - проверка команд
4. Отправьте текст - проверка сохранения

---

## 🔧 Быстрый фикс

### Бот не отвечает
```bash
# Docker
docker-compose restart

# Screen
screen -X -S obsidian-bot quit
screen -dmS obsidian-bot python3 bot.py
```

### Переустановка зависимостей
```bash
pip3 install -r requirements.txt --force-reinstall
```

### Очистка Docker
```bash
docker system prune -a            # Удалить неиспользуемые образы
docker-compose down -v            # Удалить контейнеры и volumes
```

---

## 💾 Бэкап

### Бэкап .env
```bash
cp .env .env.backup
```

### Скачать .env на ПК (PowerShell)
```bash
scp root@ваш-ip:/root/obsidian-telegram-bot/.env ./backup.env
```

---

## 🎯 Типичные сценарии

### Перезагрузка VPS
```bash
reboot
# Переподключиться через 1-2 минуты
ssh root@ваш-ip
# Проверить что бот запустился (если Docker - автоматически)
docker-compose ps
```

### Изменение токенов
```bash
nano .env                         # Изменить токены
docker-compose restart            # Перезапустить (Docker)
# ИЛИ
screen -X -S obsidian-bot quit    # Перезапустить (Screen)
screen -dmS obsidian-bot python3 bot.py
```

### Смена репозитория
```bash
nano .env                         # Изменить GITHUB_REPO
docker-compose restart            # Перезапустить
```

---

## 📞 Поддержка

Если что-то не работает:
1. Проверьте логи (`docker-compose logs` или `screen -r`)
2. Проверьте `.env` файл
3. Убедитесь что VPS подключен к интернету
4. Перезапустите бота
