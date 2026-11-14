from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html><head><title>MiniShop</title></head><body>
    <h1>MiniShop</h1>
    <div id="items">загрузка...</div>
    <input id="name" placeholder="Название товара">
    <button onclick="addItem()">Добавить</button>
    <script>
      async function load() {
        const r = await fetch('/api/items');
        const data = await r.json();
        document.getElementById('items').innerHTML =
          data.data.map(i => `<p>#${i.id}: ${i.name}</p>`).join('');
      }
      async function addItem() {
        const name = document.getElementById('name').value;
        await fetch('/api/items', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({name})
        });
        load();
      }
      load();
    </script>
    </body></html>
    """
