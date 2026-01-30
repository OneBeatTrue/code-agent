# AI Coding Agent

Автоматизированный агент для разработки кода через GitHub Issues с использованием ИИ.

## Возможности

- **Автоматическая разработка**: Анализирует GitHub Issues и создает код
- **Итеративный процесс**: До 5 итераций улучшения кода на основе ревью
- **ИИ-ревью**: Автоматическая проверка качества и соответствия требованиям
- **GitHub App**: Интеграция через GitHub App с webhook'ами
- **Поддержка LLM**: OpenAI

## Быстрый старт

1. **Настройка окружения**:
   ```bash
   cp .env.example .env
   # Заполните переменные в .env
   ```

2. **Запуск**:
   ```bash
   docker-compose up --build
   ```

3. **Использование**:
   - Создайте issue в репозитории
   - Запустите обработку: `POST /admin/run/issue/{owner}/{repo}/{issue_number}`
   - Система автоматически создаст PR с решением

## Конфигурация

Основные переменные в `.env`:

```bash
# GitHub App
GITHUB_APP_ID=your_app_id
GITHUB_APP_PRIVATE_KEY=path/to/private.pem

# LLM (выберите один)
OPENAI_API_KEY=your_openai_key

# Настройки
MAX_ITERATIONS=5
```

## API

- `GET /health` - Проверка состояния
- `POST /admin/run/issue/{owner}/{repo}/{issue_number}` - Запуск обработки issue
- `POST /admin/run/review/{owner}/{repo}/{pr_number}` - Ручной запуск ревью
- `GET /admin/iterations` - Список активных итераций
- `GET /docs` - Swagger документация

## Архитектура

```
GitHub Issue → Анализ → Генерация кода → PR → CI → ИИ-ревью → Итерация/Завершение
```
