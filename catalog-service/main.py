import os, json, time
import psycopg2
import redis
import pika
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

DB_HOST = os.getenv("DB_HOST", "postgres-master")
DB_NAME = os.getenv("DB_NAME", "appdb")
DB_USER = os.getenv("DB_USER", "appuser")
DB_PASS = os.getenv("DB_PASS", "apppass")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
RABBIT_HOSTS = os.getenv("RABBIT_HOSTS", "rabbitmq1,rabbitmq2,rabbitmq3").split(",")

def get_db():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME,
                            user=DB_USER, password=DB_PASS)

def get_redis():
    return redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

def publish(event: dict):
    last_err = None
    for host in RABBIT_HOSTS:
        try:
            conn = pika.BlockingConnection(pika.ConnectionParameters(host=host, connection_attempts=1, socket_timeout=2))
            ch = conn.channel()
            ch.queue_declare(queue="catalog_events", durable=True,
                             arguments={"x-queue-type": "quorum"})
            ch.basic_publish(exchange="", routing_key="catalog_events",
                             body=json.dumps(event),
                             properties=pika.BasicProperties(delivery_mode=2))
            conn.close()
            print(f"[catalog] published via {host}", flush=True)
            return
        except Exception as e:
            print(f"[catalog] {host} failed: {e}", flush=True)
            last_err = e
    raise RuntimeError(f"cannot publish: {last_err}")

class ItemIn(BaseModel):
    name: str

@app.get("/items")
def list_items():
    r = get_redis()
    cached = r.get("items:all")
    if cached:
        return {"source": "cache", "data": json.loads(cached)}
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT id, name FROM items ORDER BY id")
    rows = cur.fetchall(); cur.close(); conn.close()
    data = [{"id": row[0], "name": row[1]} for row in rows]
    r.setex("items:all", 60, json.dumps(data))
    return {"source": "db", "data": data}

@app.get("/items/{item_id}")
def get_item(item_id: int):
    r = get_redis()
    cached = r.get(f"item:{item_id}")
    if cached:
        return {"source": "cache", "data": json.loads(cached)}
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT id, name FROM items WHERE id=%s", (item_id,))
    row = cur.fetchone(); cur.close(); conn.close()
    if not row:
        raise HTTPException(404, "not found")
    data = {"id": row[0], "name": row[1]}
    r.setex(f"item:{item_id}", 60, json.dumps(data))
    return {"source": "db", "data": data}

@app.post("/items")
def create_item(item: ItemIn):
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO items (name) VALUES (%s) RETURNING id, name", (item.name,))
    row = cur.fetchone(); conn.commit(); cur.close(); conn.close()
    data = {"id": row[0], "name": row[1]}
    r = get_redis()
    r.delete("items:all"); r.delete(f"item:{row[0]}")
    publish({"event": "item_created", "item": data})
    return data

@app.put("/items/{item_id}")
def update_item(item_id: int, item: ItemIn):
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE items SET name=%s WHERE id=%s RETURNING id, name",
                (item.name, item_id))
    row = cur.fetchone(); conn.commit(); cur.close(); conn.close()
    if not row:
        raise HTTPException(404, "not found")
    data = {"id": row[0], "name": row[1]}
    r = get_redis()
    r.delete("items:all"); r.delete(f"item:{item_id}")
    publish({"event": "item_updated", "item": data})
    return data

@app.delete("/items/{item_id}")
def delete_item(item_id: int):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM items WHERE id=%s RETURNING id", (item_id,))
    row = cur.fetchone(); conn.commit(); cur.close(); conn.close()
    if not row:
        raise HTTPException(404, "not found")
    r = get_redis()
    r.delete("items:all"); r.delete(f"item:{item_id}")
    publish({"event": "item_deleted", "item": {"id": item_id}})
    return {"deleted": item_id}
