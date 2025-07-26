# web.py
import os
import re
from flask import Flask, request
import requests
from process import process_images, list_templates

from werkzeug.utils import secure_filename

BOT_TOKEN = os.environ.get("BOT_TOKEN")
app = Flask(__name__)

user_states = {}  # to track template choice and max height per user
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Send message
def send_telegram(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, data=payload)

# Send photo
def send_photo(chat_id, image_path):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with open(image_path, "rb") as img:
        requests.post(url, data={"chat_id": chat_id}, files={"photo": img})

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.json
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")

    # File/image handling
    if "photo" in message:
        if chat_id not in user_states:
            send_telegram(chat_id, "❗ Please start with /start")
            return {"ok": True}

        # Ask for max height if not given
        if "max_height" not in user_states[chat_id]:
            send_telegram(chat_id, "📏 Enter max height first (e.g. 1200)")
            return {"ok": True}

        # Get highest resolution photo
        photo_list = message["photo"]
        file_id = photo_list[-1]["file_id"]
        file_path = get_file_path(file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

        # Download
        local_filename = os.path.join(UPLOAD_FOLDER, secure_filename(file_id + ".jpg"))
        with open(local_filename, "wb") as f:
            f.write(requests.get(file_url).content)

        # Process image
        output_path = process_images(
            [local_filename],
            user_states[chat_id]["template"],
            user_states[chat_id]["max_height"]
        )[0]  # one image only

        send_photo(chat_id, output_path)
        os.remove(local_filename)
        os.remove(output_path)
        return {"ok": True}

    # Handle text
    text = message.get("text", "")

    if text.startswith("/start"):
        templates = list_templates()
        msg = "🖼 Choose a template by replying with its number:\n"
        for i, t in enumerate(templates, 1):
            msg += f"{i}. {t}\n"
        user_states[chat_id] = {"stage": "awaiting_template"}
        send_telegram(chat_id, msg)

    elif chat_id in user_states and user_states[chat_id].get("stage") == "awaiting_template":
        templates = list_templates()
        try:
            choice = int(text.strip())
            if 1 <= choice <= len(templates):
                user_states[chat_id] = {
                    "template": os.path.join("templates", templates[choice - 1]),
                    "stage": "awaiting_height"
                }
                send_telegram(chat_id, "📏 Now enter max product height (e.g. 1200):")
            else:
                send_telegram(chat_id, "❌ Invalid choice. Try again.")
        except:
            send_telegram(chat_id, "❌ Please enter a valid number.")

    elif chat_id in user_states and user_states[chat_id].get("stage") == "awaiting_height":
        try:
            height = int(text.strip())
            user_states[chat_id]["max_height"] = height
            user_states[chat_id]["stage"] = "ready"
            send_telegram(chat_id, "✅ Great! Now send product image(s). I will remove BG and paste on your template.")
        except:
            send_telegram(chat_id, "❌ Invalid height. Enter a number like 1200")

    else:
        send_telegram(chat_id, "❓ I didn’t understand. Please use /start to begin.")

    return {"ok": True}

@app.route("/")
def home():
    return "✅ Affiliate Template Bot Running"

def get_file_path(file_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
    return requests.get(url).json()["result"]["file_path"]

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
