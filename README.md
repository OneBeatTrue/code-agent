# AI Code Agent

Автоматизированный агент для разработки кода через GitHub App.

## Запуск

1. **Настройка окружения**:
   ```bash
   .env
   ```

2. **Запуск (как это работает на сервере)**:
   ```bash
   docker-compose up --build
   ```

3. **Использование**:
   - Добавьте приложение в свой репозиторий по ссылке https://github.com/apps/ai-code-agent-by-obt
   - Создайте issue в репозитории
   - Система автоматически создаст PR с решением

## Конфигурация в `.env` (обязательная)

```bash
GITHUB_APP_ID=your_app_id
GITHUB_APP_PRIVATE_KEY=path/to/private.pem

OPENAI_API_KEY=your_openai_key
OPENAI_BASE_URL=your_openai_provider_url
OPENAI_BASE_URL=your_openai_provider_url

```

## Репозиторий со скриптами для автоматического CD приложения

https://github.com/OneBeatTrue/code-agent-deploy
