Write-Host "Запускается обучение модели Rasa в изолированном контейнере..."
docker run --rm -v "${PWD}/rasa_bot:/app" rasa/rasa:3.6.20-full train
Write-Host "Обучение завершено. Новая модель сохранена в rasa_bot/models"
