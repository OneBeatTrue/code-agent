# AI Code Agent

Автоматизированный агент для разработки кода через GitHub App.

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

## Конфигурация в `.env` (обязательная)

```bash
GITHUB_APP_ID=your_app_id
GITHUB_APP_PRIVATE_KEY=path/to/private.pem

OPENAI_API_KEY=your_openai_key
OPENAI_BASE_URL=your_openai_provider_url
OPENAI_BASE_URL=your_openai_provider_url

```
