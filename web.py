# web.py

import os
import re
from flask import Flask, request
import requests
from werkzeug.utils import secure_filename
from process import process_images, list_templates

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN env variable not found")

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

user_states = {}

def send_telegram(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json()
    if not update:
        return {"ok": False}

    message = update.get("message")
    if not message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]

    if "text" in message:
        text = message["text"]

        if text == "/start":
            send_telegram(chat_id, "👋 Welcome! Send an image to start.")
            user_states[user_id] = {}
        elif text.startswith("/template"):
            templates = list_templates()
            send_telegram(chat_id, "🖼 Available templates:\n" + "\n".join(templates))
        elif re.match(r"/set (\d+)", text):
            height = int(text.split()[1])
            user_states[user_id]["max_height"] = height
            send_telegram(chat_id, f"✅ Max height set to {height}px.")
        elif text.startswith("/use"):
            template = text.split()[1]
            user_states[user_id]["template"] = template
            send_telegram(chat_id, f"✅ Template set to {template}.")
        else:
            send_telegram(chat_id, "❓ Unknown command.")
        return {"ok": True}

    if "photo" in message:
        file_id = message["photo"][-1]["file_id"]
        file_info = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}").json()
        file_path = file_info["result"]["file_path"]

        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        filename = secure_filename(file_path.split("/")[-1])
        local_path = os.path.join(UPLOAD_FOLDER, filename)

        with open(local_path, "wb") as f:
            f.write(requests.get(file_url).content)

        user_prefs = user_states.get(user_id, {})
        template = user_prefs.get("template")
        max_height = user_prefs.get("max_height")

        try:
            output_paths = process_images([local_path], template, max_height)  # 🔁 Pass as list
            for output_path in output_paths:
                with open(output_path, "rb") as f:
                    files = {"photo": f}
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto", data={"chat_id": chat_id}, files=files)
        except Exception as e:
            send_telegram(chat_id, f"❌ Error: {str(e)}")

    return {"ok": True}

@app.route("/")
def home():
    return "✅ Bot is alive."

# Vercel expects `app` object to be present
app = app
