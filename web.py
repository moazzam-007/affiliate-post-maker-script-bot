import os
import shelve  # 're' ki jagah shelve import kiya
from flask import Flask, request
import requests
from werkzeug.utils import secure_filename

# Yeh assume kiya ja raha hai ki 'process.py' file maujood hai
from process import process_images, list_templates

# --- Environment Config ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Error: BOT_TOKEN environment variable set nahi hai.")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Flask App Init ---
app = Flask(__name__)

# --- Telegram Helper Functions ---
def send_telegram(chat_id, text):
    """Telegram par text message bhejta hai."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, data=payload)
    except requests.exceptions.RequestException as e:
        print(f"Error sending message to {chat_id}: {e}")

def send_photo(chat_id, image_path):
    """Telegram par photo bhejta hai."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with open(image_path, "rb") as img:
        try:
            requests.post(url, data={"chat_id": chat_id}, files={"photo": img})
        except requests.exceptions.RequestException as e:
            print(f"Error sending photo to {chat_id}: {e}")

def get_file_path(file_id):
    """Telegram se file ka path get karta hai (Error handling ke saath)."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # HTTP errors ke liye exception raise karega
        data = response.json()
        if data.get("ok"):
            return data.get("result", {}).get("file_path")
    except requests.exceptions.RequestException as e:
        print(f"Error getting file path from Telegram: {e}")
    return None

# --- Main Webhook ---
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.json
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")

    if not chat_id:
        return {"ok": True}

    # Shelve ka istemal state ko file mein save karne ke liye
    with shelve.open("user_states.db") as user_states:
        # State ko handle karne wala logic
        handle_message(chat_id, message, user_states)

    return {"ok": True}

def handle_message(chat_id, message, user_states):
    """Message processing ka saara logic is function mein hai."""
    # Text message handling
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

    # Photo handling
    elif "photo" in message:
        current_state = user_states.get(str(chat_id), {})
        if current_state.get("stage") != "ready":
            send_telegram(chat_id, "❗ Pehle /start command se process poora karein.")
            return

        file_id = message["photo"][-1]["file_id"]
        file_path = get_file_path(file_id)
        if not file_path:
            send_telegram(chat_id, "❌ Server se file download karne mein problem aa rahi hai. Dobara try karein.")
            return

        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        local_filename = os.path.join(UPLOAD_FOLDER, secure_filename(file_id + ".jpg"))
        output_path = ""

        try:
            # File download karna
            with open(local_filename, "wb") as f:
                f.write(requests.get(file_url).content)

            # Image process karna
            output_path = process_images(
                [local_filename],
                current_state["template"],
                current_state["max_height"]
            )[0]

            # Processed photo bhejna
            send_photo(chat_id, output_path)

        except Exception as e:
            print(f"Error during file processing/sending for chat {chat_id}: {e}")
            send_telegram(chat_id, "⚙️ Image process karte waqt ek error aa gaya.")
        finally:
            # Temporary files ko hamesha delete karna, chahe error aaye ya na aaye
            if os.path.exists(local_filename):
                os.remove(local_filename)
            if output_path and os.path.exists(output_path):
                os.remove(output_path)

# --- Health Check Route ---
@app.route("/")
def home():
    return "✅ Affiliate Template Bot Running"

# --- Flask App Port Binding (Sahi Indentation Ke Saath) ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"✅ Starting Flask app on port {port}")
    app.run(host="0.0.0.0", port=port, debug=True) # debug=True local testing ke liye
