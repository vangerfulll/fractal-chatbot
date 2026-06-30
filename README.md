# Fractal Club Chatbot

FastAPI webhook server for JivoSite Bot API with Rasa NLU, Redis sessions, and HolliHop CRM integration.

## Quick deploy

1. Create server env file:

   ```bash
   cp .env.example .env
   nano .env
   ```

2. Fill required production values:

   ```env
   APP_ENV=production
   MOCK_EXTERNAL_APIS=false
   JIVO_PROVIDER_ID=...
   JIVO_BOT_TOKEN=...
   HOLLIHOP_DOMAIN=https://your-school.hollihop.ru/
   HOLLIHOP_API_KEY=...
   ```

3. Train Rasa model:

   ```bash
   docker compose -p fractal-chatbot --env-file .env --profile tools run --rm rasa-train
   ```

4. Start services:

   ```bash
   docker compose -p fractal-chatbot --env-file .env up -d --build
   ```

5. Check health:

   ```bash
   curl http://localhost:8000/health/live
   curl http://localhost:8000/health/ready
   ```

6. Configure Jivo bot provider endpoint:

   ```text
   https://YOUR_DOMAIN/webhook/jivosite/JIVO_BOT_TOKEN
   ```

## Local checks

```bash
python -m unittest discover -s tests
python -m compileall main.py hollihop_client.py dialog_manager.py app/core/config.py
```

## Notes

- Redis and Rasa are internal Docker services and are not published to the internet.
- The public service is FastAPI on port `8000`; put Nginx/Caddy in front of it for HTTPS.
- `HOLLIHOP_DOMAIN` must be the school subdomain root, for example `https://school.hollihop.ru/`.
