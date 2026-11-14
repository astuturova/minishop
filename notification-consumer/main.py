import os, json, time
import pika

RABBIT_HOSTS = os.getenv("RABBIT_HOSTS", "rabbitmq1,rabbitmq2,rabbitmq3").split(",")

def callback(ch, method, props, body):
    event = json.loads(body)
    print(f"[consumer] received: {event}", flush=True)
    ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    for attempt in range(60):
        for host in RABBIT_HOSTS:
            try:
                conn = pika.BlockingConnection(pika.ConnectionParameters(host=host, connection_attempts=1, socket_timeout=2))
                ch = conn.channel()
                ch.queue_declare(queue="catalog_events", durable=True,
                                 arguments={"x-queue-type": "quorum"})
                ch.basic_consume(queue="catalog_events", on_message_callback=callback)
                print(f"[consumer] connected to {host}, waiting...", flush=True)
                ch.start_consuming()
                return
            except Exception as e:
                print(f"[consumer] {host} failed: {e}", flush=True)
        time.sleep(2)

if __name__ == "__main__":
    main()
