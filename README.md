# mailman

# 📬 MAILMAN

**MAILMAN** — сервис массовых рассылок рекламных и информационных сообщений через мессенджеры **Telegram** и **MAX**, глубоко интегрированный с **Битрикс24 (BX24)**.

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                        Битрикс24                            │
│  Список 451 (шаблоны)    Список 449 (статистика)   Чат     │
└────────────┬────────────────────────┬─────────────────┬─────┘
             │ REST API               │                 │
┌────────────▼────────────────────────▼─────────────────▼─────┐
│                    MAILMAN (FastAPI)                         │
│  /api/mass-mailing-telegram   /api/mass-mailing-max         │
│  /api/updater-list            /api/validate-email           │
└────────────────────────┬────────────────────────────────────┘
                         │ Celery Tasks
              ┌──────────▼──────────┐
              │   Redis (Broker)    │
              └──────────┬──────────┘
              ┌──────────▼──────────┐
              │   Celery Worker     │◄─── Flower (мониторинг)
              │  Батчевая отправка  │
              └──────┬──────┬───────┘
                     │      │
           ┌─────────▼─┐  ┌─▼──────────┐
           │  Telegram  │  │    MAX     │
           │    Bot     │  │    Bot     │
           └────────────┘  └────────────┘
```

**Стек технологий:**

| Компонент   | Технология                          |
|-------------|-------------------------------------|
| Backend     | Python 3.11+, FastAPI, Uvicorn      |
| Task Queue  | Celery + Redis                      |
| Scheduler   | APScheduler (фоновые задачи)        |
| Database    | MySQL (SQLAlchemy ORM)              |
| Email       | SendGrid Validation API             |
| Monitoring  | Flower (Celery UI), Loguru logs     |
| Deploy      | Docker Compose + Nginx + Let's Encrypt |

---

## 📡 API Endpoints

### Рассылки (Production)

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/mass-mailing-telegram` | Telegram рассылка по шаблону из BX24 |
| `POST` | `/api/mass-mailing-telegram` | Telegram рассылка с произвольным текстом |
| `GET` | `/api/mass-mailing-max` | MAX рассылка по шаблону из BX24 |
| `POST` | `/api/mass-mailing-max` | MAX рассылка с произвольным текстом |
| `GET` | `/api/task-status/{task_id}` | Статус задачи Celery |

### Тестовые рассылки

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/mass-mailing-telegram-test` | Telegram тест (тестовые пользователи) |
| `GET` | `/api/mass-mailing-max-test` | MAX тест (тестовые пользователи) |

### Утилиты

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/updater-list` | Обновить счётчик в BX24 Список 449 |
| `GET` | `/api/validate-email` | Валидация email через SendGrid |

### Документация

| Путь | Описание |
|------|----------|
| `/docs` | Swagger UI (Basic Auth) |
| `/redoc` | ReDoc UI (Basic Auth) |

---

## 🔑 Параметры рассылки (GET-запросы)

| Параметр | Тип | Описание |
|----------|-----|----------|
| `element_id_451` | int/str | ID элемента в Списке 451 BX24 (приоритетный) |
| `element_name_451` | str | NAME элемента в Списке 451 BX24 |
| `element_buttons_451` | bool | Использовать кнопки из Списка 451 (default: false) |
| `expat` | bool | `true` — экспаты, `false` — пользователи РФ |

**Пример:**
```
GET /api/mass-mailing-telegram?element_id_451=42&expat=false&element_buttons_451=true
```

---

## 🗄️ Структура базы данных

| Таблица | Назначение |
|---------|------------|
| `GPS_leads` | Лиды CRM Битрикс24 |
| `lms_users` | Пользователи LMS (статус обучения, баланс, часовой пояс) |
| `max_users` | Пользователи MAX мессенджера (chat_id ↔ lead_id) |
| `tg_customer_links` | Привязка Telegram chat_id к пользователям LMS |
| `max_leads_rejection` | Актуальный список получателей MAX рассылки |
| `telegram_leads_rejection` | Актуальный список получателей Telegram рассылки |

**Критерии попадания в список рассылки:**
- `is_study = 0` — пользователь не обучается
- `balance_user = 0` — нулевой баланс (только Telegram)
- `next_lesson_date = NULL` — нет запланированных уроков (только Telegram)
- `id_contact IS NULL` — не является контактом (только Telegram)

**Определение экспата:**
- Номер телефона **не** начинается с `8`, `+7`, `7` **ИЛИ**
- Часовой пояс **не** `Europe/Moscow`

---

## ⏰ Расписание автозадач

Каждый день в **6:00 UTC+3 (МСК)**:

| Время | Задача |
|-------|--------|
| 06:00 | Пересборка таблицы `max_leads_rejection` |
| 06:05 | Обновление счётчиков в Bitrix24 Список 449 |
| 06:10 | Пересборка таблицы `telegram_leads_rejection` |

---

## 🔗 Интеграция с Битрикс24

| Список BX24 | ID | Назначение | Свойства |
|-------------|-----|------------|---------|
| Шаблоны рассылок | `451` | Хранит тексты и кнопки | `PROPERTY_2295` (текст), `PROPERTY_2301` (кнопки JSON) |
| Статистика | `449` | Хранит счётчики аудитории | `PROPERTY_2297` (количество), `PROPERTY_2299` (ID сегмента) |

**ID сегментов Bitrix24:**

| Сегмент | ID |
|---------|----|
| MAX (РФ) | 2349 |
| MAX (Экспаты) | 2347 |
| Telegram (РФ) | 2345 |
| Telegram (Экспаты) | 2343 |
| MAX Test | 2353 |
| Telegram Test | 2351 |

После завершения рассылки — **автоматическое уведомление в чат BX24** `chat1580889` со статистикой.

---

## 🚀 Развёртывание

### Требования
- Docker + Docker Compose
- Домен с DNS A-записью

### Переменные окружения (`.env`)


### Запуск

```bash
# Первый запуск
git clone <repo>
cd mailman
cp .env.example .env   # заполнить переменные
docker-compose up --build -d

# Обновление
git pull
docker-compose up --build -d
```

### Обновление на сервере

```bash
vim .env           # при необходимости правим переменные (:wq для сохранения)
git pull
docker-compose up --build -d
```
---

## 📊 Мониторинг

- **Flower** — веб-интерфейс для мониторинга очередей Celery: `http://server:5555`
- **Логи** — хранятся 30 дней с ротацией по полуночи, сжаты в zip
  - `logs/debug/` — все события (DEBUG+)
  - `logs/info/` — информационные события (INFO+)
- **Статус задачи** — `GET /api/task-status/{task_id}`

---

## 🔒 Безопасность

- Swagger/ReDoc защищены **Basic Auth**
- В production OpenAPI schema недоступна (`/openapi.json` отключён)
- Все секреты — через `.env` файл, не хранятся в репозитории
- HTTPS через **Let's Encrypt** (автообновление сертификатов через Nginx)

---