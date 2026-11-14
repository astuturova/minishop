CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);
INSERT INTO items (name) VALUES ('Ноутбук'), ('Наушники');
