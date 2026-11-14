# MiniShop — учебный MVP интернет-магазина на микросервисах

**Студент:** Анастасия Тутурова  
**Курс:** Безопасность высоконагруженных систем (ВШЭ × VK Education)  
**Точка контроля:** промежуточная защита проекта (коллоквиум, ноябрь 2026)

---

## 1. Описание проекта

**MiniShop** — учебный интернет-магазин, реализованный как набор микросервисов.  
Цель — показать безопасную, отказоустойчивую и воспроизводимую микросервисную архитектуру с изоляцией сетей, кэшированием, асинхронной обработкой событий и репликацией данных.

### Зачем микросервисы (обоснование)
- **Каталог** — read-heavy нагрузка: много чтений, редкие записи → кэшируем в Redis, БД защищена.
- **Уведомления о новых товарах** — не должны блокировать запись каталога → выносим в отдельный consumer через RabbitMQ (асинхронно, с гарантией доставки).
- **Безопасность** — данные каталога (PostgreSQL, Redis, RabbitMQ) не доступны фронтенду напрямую → сегментация сетей + API Gateway (nginx).
- **Надёжность** — PostgreSQL с репликацией master/standby; RabbitMQ — кластер из 3 узлов с quorum queues (Raft); резервное копирование БД.

---

## 2. Архитектура

### 2.1 Сервисы

| Компонент | Роль | Технологии |
|---|---|---|
| `nginx` | API Gateway, единая точка входа | nginx:alpine |
| `frontend` | UI каталога (HTML + JS) | FastAPI, Python 3.11 |
| `catalog-service` | CRUD товаров, кэш, публикация событий | FastAPI, psycopg2, redis-py, pika |
| `notification-consumer` | Потребление событий, логирование | Python, pika |
| `postgres-master` / `postgres-standby` | БД с потоковой репликацией | PostgreSQL 16 (alpine) |
| `rabbitmq1/2/3` | Кластер брокера, quorum queues | RabbitMQ 3.13 |
| `redis` | Кэш | Redis 7 (alpine) |

### 2.2 Схема взаимодействия

```mermaid
flowchart LR
    User([Пользователь])

    subgraph public_net["public_net (вход извне)"]
        Nginx["nginx<br/>API Gateway :80"]
        Frontend["frontend :8000"]
    end

    subgraph app_net["app_net (внутренние API)"]
        Catalog["catalog-service :8001"]
    end

    subgraph data_net["data_net (internal: true)"]
        PG[("PostgreSQL<br/>master + standby")]
        Redis[("Redis<br/>cache")]
        RMQ[("RabbitMQ cluster<br/>3 nodes, quorum")]
        Consumer["notification-consumer"]
    end

    User -->|HTTP| Nginx
    Nginx -->|"/"| Frontend
    Nginx -->|"/api/*"| Catalog
    Catalog -->|SQL| PG
    Catalog -->|cache| Redis
    Catalog -->|publish| RMQ
    RMQ -->|consume| Consumer


### 2.3 Сетевые сегменты

| Сегмент | Кто в нём | Назначение |
|---|---|---|
| `public_net` | nginx, frontend | Вход извне |
| `app_net` | nginx, catalog-service | Внутренние API |
| `data_net` (`internal: true`) | catalog-service, consumer, postgres, redis, rabbit | Данные, нет выхода наружу |

### 2.4 Матрица доступа (firewall-правила)

| Источник → Назначение | Правило |
|---|---|
| frontend → nginx | ALLOW (HTTP) |
| nginx → catalog-service | ALLOW (HTTP :8001) |
| catalog-service → postgres-master | ALLOW (TCP :5432) |
| catalog-service → redis | ALLOW (TCP :6379) |
| catalog-service → rabbitmq1/2/3 | ALLOW (TCP :5672) |
| notification-consumer → rabbitmq1/2/3 | ALLOW (TCP :5672) |
| frontend → catalog-service | **DENY** |
| nginx → postgres | **DENY** |
| frontend → postgres/redis/rabbit | **DENY** |

Правила реализуются средствами Docker networks (iptables на хосте): контейнеры в `data_net` не видят `public_net`, `frontend` — не видит `data_net`. `data_net` помечена `internal: true` — нет выхода в интернет.

---

## 3. Запуск

```bash
docker compose up --build -d
docker compose ps
