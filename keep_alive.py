from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    # Replit's default port is 8080. Other platforms might use 5000 or an environment variable.
    # For Replit, 0.0.0.0 and 8080 are correct.
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
