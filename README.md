# Чат-рулетка бот для Telegram

## Структура файлов

```
bot.py          — основной файл, хендлеры
matcher.py      — логика очереди и сессий (Redis)
keyboards.py    — клавиатуры
config.py       — настройки
requirements.txt
```

## Быстрый старт

### 1. Установи зависимости
```bash
pip install -r requirements.txt
```

### 2. Запусти Redis
```bash
# Через Docker (проще всего)
docker run -d -p 6379:6379 redis:alpine
```

### 3. Создай бота
Напиши @BotFather в Telegram → /newbot → скопируй токен

### 4. Запусти
```bash
BOT_TOKEN=твой_токен python bot.py
```

## Деплой на VPS (Ubuntu)

```bash
# Установка
apt install python3-pip redis-server -y
pip install -r requirements.txt

# Запуск через systemd
nano /etc/systemd/system/chatbot.service
```

```ini
[Unit]
Description=Chat Roulette Bot
After=network.target redis.service

[Service]
WorkingDirectory=/opt/chatbot
ExecStart=/usr/bin/python3 bot.py
Environment=BOT_TOKEN=твой_токен
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable chatbot
systemctl start chatbot
```

## Как работает матчинг

1. Пользователь нажимает "Найти" → `enqueue(user_id)`
2. Если кто-то уже в очереди → создаётся сессия (`create_session`)
3. Все сообщения → `get_partner(user_id)` → `bot.copy_message(partner_id)`
4. `copy_message` сохраняет анонимность — user_id нигде не передаётся

## Redis-схема

```
waiting_queue          ZSET   — очередь (score = timestamp)
session:{uid}          STRING — partner_id текущего собеседника
banned:{uid}           STRING — флаг бана (expire = длительность)
reports:{uid}          SET    — кто пожаловался (TTL 7 дней)
users                  SET    — все пользователи
msg_count:{uid}        STRING — счётчик сообщений за сутки
```

## Что добавить дальше

- [ ] Фильтр по теме (добавить параметр в `enqueue`)
- [ ] Telegram Stars для снятия лимитов
- [ ] Статистика `/stats` для админа
- [ ] Автомодерация через Perspective API
- [ ] Уведомление «онлайн сейчас X человек»
