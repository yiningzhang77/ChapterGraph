# ECS Single-Host Deploy

This setup runs the full app on one ECS host:

- `web` serves the frontend on port `80`
- `web` proxies `/api/*` to the FastAPI backend
- `db` runs PostgreSQL on the internal Docker network only

Because the browser talks to the same origin, this layout avoids CORS entirely.

## 1. Prepare env

On the server:

```bash
cd /srv/chaptergraph/app/deploy/ecs
cp .env.example .env
nano .env
```

Minimum changes:

- set `POSTGRES_PASSWORD`
- choose real `QWEN_*` values if not using `stub`

## 2. Start the stack

```bash
cd /srv/chaptergraph/app/deploy/ecs
docker compose up -d --build
docker compose ps
```

Health check after startup:

```bash
curl http://127.0.0.1/
curl http://127.0.0.1/api/healthz
curl http://127.0.0.1/api/readyz
```

## 3. Restore your local PostgreSQL data

From your local machine:

```bash
pg_dump -h localhost -U postgres -d chaptergraph -Fc -f chaptergraph.dump
scp chaptergraph.dump root@YOUR_SERVER_IP:/srv/chaptergraph/
```

On the server:

```bash
cd /srv/chaptergraph/app/deploy/ecs
cat /srv/chaptergraph/chaptergraph.dump | docker compose exec -T db \
  pg_restore --clean --if-exists --no-owner --no-privileges \
  -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

Then verify:

```bash
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT COUNT(*) FROM run;"
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT COUNT(*) FROM edge;"
```

## 4. Update later

```bash
cd /srv/chaptergraph/app
git pull
cd deploy/ecs
docker compose up -d --build
```
