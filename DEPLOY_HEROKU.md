# Celamur — деплой на Heroku

## Что потребуется
- Аккаунт Heroku
- Heroku CLI
- Git
- Подключённый к приложению Heroku Postgres

## 1. Установка Heroku CLI (macOS)

```bash
brew tap heroku/brew && brew install heroku
heroku login
```

## 2. Подготовить приложение

Распакуйте архив и перейдите в папку `celamur-v10` (там, где лежит `app.py`):

```bash
cd путь/к/celamur-v10
```

Проверьте, что Procfile, requirements.txt и app.py лежат прямо в этой папке:

```bash
ls
```

## 3. Выбрать существующее приложение Heroku или создать новое

Посмотреть приложения:

```bash
heroku apps
```

Если приложение уже создано, укажите его имя вместо `YOUR_APP_NAME` во всех командах ниже:

```bash
heroku git:remote -a YOUR_APP_NAME
```

Если приложения ещё нет, создайте:

```bash
heroku create YOUR_APP_NAME
```

## 4. Подключить PostgreSQL

Сначала проверьте, не подключена ли база:

```bash
heroku addons -a YOUR_APP_NAME
```

Если `heroku-postgresql` ещё нет, создайте её:

```bash
heroku addons:create heroku-postgresql:essential-0 -a YOUR_APP_NAME
heroku pg:wait -a YOUR_APP_NAME
```

План Essential-0 платный (ориентировочно до $5/месяц по текущей документации; проверьте цену перед подтверждением). После подключения Heroku автоматически задаёт `DATABASE_URL`.

## 5. Перенести существующие письма из SQLite (если нужно)

Архив содержит локальный `letters.sqlite3`, но он намеренно исключён из Git. Чтобы сохранить уже созданные письма, сначала разверните приложение и подключите PostgreSQL, затем в этой же локальной папке выполните:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="$(heroku config:get DATABASE_URL -a YOUR_APP_NAME)"
python migrate_sqlite_to_postgres.py
```

Не публикуйте `DATABASE_URL` и не отправляйте его в чаты. Если старые письма не нужны, этот шаг можно пропустить.

## 6. Деплой

Если папка ещё не является Git-репозиторием:

```bash
git init
git add .
git commit -m "Deploy Celamur to Heroku"
heroku git:remote -a YOUR_APP_NAME
```

Если Git уже настроен, просто добавьте изменения и создайте commit:

```bash
git add .
git commit -m "Prepare Celamur for Heroku"
```

Отправьте код:

```bash
git push heroku main
```

Если локальная ветка называется `master`, используйте `git push heroku master:main`.

Запустите web dyno и откройте сайт:

```bash
heroku ps:scale web=1 -a YOUR_APP_NAME
heroku open -a YOUR_APP_NAME
```

## 7. Проверка и логи

Откройте `https://YOUR_APP_NAME.herokuapp.com/health` — ожидается:

```json
{"status":"ok"}
```

Логи:

```bash
heroku logs --tail -a YOUR_APP_NAME
```

## Важно
- Приложение слушает порт из `$PORT`, как требует Heroku.
- В production используется `DATABASE_URL` от Heroku Postgres; локально без неё продолжает работать SQLite.
- Не добавляйте `.env`, `DATABASE_URL` или `letters.sqlite3` в Git.
- Heroku Postgres Essential-0 и dyno могут быть платными. Перед подтверждением проверьте текущие цены и план dyno в панели Heroku.
