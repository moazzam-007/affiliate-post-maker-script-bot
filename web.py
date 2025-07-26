import os
import shelve
from flask import Flask, request
import requests
from werkzeug.utils import secure_filename

from process import process_images, list_templates

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Error: BOT_TOKEN environment variable set nahi hai.")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)

def send_telegram(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": chat_id, "text": text})
    except Exception as e:
        print(f"[send_telegram] Error: {e}")

def send_photo(chat_id, image_path):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with open(image_path, "rb") as img:
        try:
            requests.post(url, data={"chat_id": chat_id}, files={"photo": img})
        except Exception as e:
            print(f"[send_photo] Error: {e}")

def get_file_path(file_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get("result", {}).get("file_path")
    except Exception as e:
        print(f"[get_file_path] Error: {e}")
        return None

@app.route("/", methods=["GET"])
def home():
    return "✅ Affiliate Template Bot Running"

# 🔄 Accept Telegram updates on both "/" and "/<BOT_TOKEN>"
@app.route("/", methods=["POST"])
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.json
    chat_id = data.get("message", {}).get("chat", {}).get("id")
    if not chat_id:
        return {"ok": True}

    with shelve.open("user_states.db") as user_states:
        handle_message(chat_id, data.get("message", {}), user_states)

    return {"ok": True}

def handle_message(chat_id, message, user_states):
    if "text" in message:
        text = message.get("text", "")
        current_state = user_states.get(str(chat_id), {})
        stage = current_state.get("stage")

        if text.startswith("/start"):
            templates = list_templates()
            msg = "🖼️ Template choose karein, uska number reply karke:\n"
            for i, t in enumerate(templates, 1):
                msg += f"{i}. {t}\n"
            user_states[str(chat_id)] = {"stage": "awaiting_template"}
            send_telegram(chat_id, msg)

        elif stage == "awaiting_template":
            templates = list_templates()
            try:
                choice = int(text.strip())
                if 1 <= choice <= len(templates):
                    current_state["template"] = os.path.join("templates", templates[choice - 1])
                    current_state["stage"] = "awaiting_height"
                    user_states[str(chat_id)] = current_state
                    send_telegram(chat_id, "📏 Ab product ki max height enter karein (e.g., 1200):")
                else:
                    send_telegram(chat_id, "❌ Invalid choice. Sahi number enter karein.")
            except ValueError:
                send_telegram(chat_id, "❌ Please ek valid number enter karein.")

        elif stage == "awaiting_height":
            try:
                height = int(text.strip())
                current_state["max_height"] = height
                current_state["stage"] = "ready"
                user_states[str(chat_id)] = current_state
                send_telegram(chat_id, "✅ Tayyar! Ab product ki image bhejein.")
            except ValueError:
                send_telegram(chat_id, "❌ Invalid height. Ek number enter karein jaise 1200.")

        else:
            send_telegram(chat_id, "❓ Samajh nahi aaya. Shuru karne ke liye /start use karein.")

    elif "photo" in message:
        current_state = user_states.get(str(chat_id), {})
        if current_state.get("stage") != "ready":
            send_telegram(chat_id, "❗ Pehle /start command se process poora karein.")
            return

        file_id = message["photo"][-1]["file_id"]
        file_path = get_file_path(file_id)
        if not file_path:
            send_telegram(chat_id, "❌ File download mein problem. Dobara try karein.")
            return

        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        local_filename = os.path.join(UPLOAD_FOLDER, secure_filename(file_id + ".jpg"))
        output_path = ""

        try:
            with open(local_filename, "wb") as f:
                f.write(requests.get(file_url).content)

            output_path = process_images(
                [local_filename],
                current_state["template"],
                current_state["max_height"]
            )[0]

            send_photo(chat_id, output_path)

        except Exception as e:
            print(f"[handle_message] Error processing image: {e}")
            send_telegram(chat_id, "⚙️ Image process karte waqt error aaya.")
        finally:
            if os.path.exists(local_filename):
                os.remove(local_filename)
            if output_path and os.path.exists(output_path):
                os.remove(output_path)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"✅ Starting Flask app on port {port}")
    app.run(host="0.0.0.0", port=port, debug=True)
