# ⚡ Быстрый старт на VPS

Самый короткий путь к запуску бота на VPS.

---

## 📋 Что нужно

1. VPS с Ubuntu (Timeweb/Selectel/DigitalOcean)
2. SSH доступ (IP, root, пароль)
3. 5 минут времени

---

## 🚀 Запуск (3 простых шага)

### 1️⃣ Подключитесь к VPS

```bash
ssh root@ваш-ip-адрес
```

### 2️⃣ Загрузите проект

```bash
cd /root
git clone https://github.com/mkoval-pwork/obsidian-telegram-bot.git
cd obsidian-telegram-bot
```

### 3️⃣ Создайте .env файл

```bash
nano .env
```

Вставьте (замените на ваши данные):

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
ALLOWED_USER_ID=your_telegram_user_id
GITHUB_TOKEN=your_github_token_here
GITHUB_REPO=username/repository
```

Сохраните: `Ctrl+X` → `Y` → `Enter`

### 4️⃣ Запустите деплой скрипт

```bash
chmod +x deploy.sh
./deploy.sh
```

Выберите:
- `1` для Docker (рекомендуется)
- `2` для Screen

---

## ✅ Готово!

Бот запущен! Протестируйте в Telegram.

---

## 📚 Подробная инструкция

Читайте **DEPLOY_VPS.md** для детальной информации.

---

## 🔄 Управление

### Docker:
```bash
docker-compose logs -f obsidian-bot  # Логи
docker-compose restart               # Перезапуск
docker-compose stop                  # Остановка
```

### Screen:
```bash
screen -r obsidian-bot  # Подключиться
screen -ls              # Список сессий
# Ctrl+A, затем D - отключиться
```

---

## 🆘 Проблемы?

```bash
# Проверить .env
cat .env

# Проверить логи (Docker)
docker-compose logs --tail=50 obsidian-bot

# Подключиться к боту (Screen)
screen -r obsidian-bot
```
