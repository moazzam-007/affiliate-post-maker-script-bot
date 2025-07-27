import os
import requests
import logging
from flask import Flask, request
from werkzeug.utils import secure_filename
from pathlib import Path

# Custom module se functions import karein
from process import process_images, list_templates

# Logging setup karein
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Configuration ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ Error: BOT_TOKEN environment variable set nahi hai.")

# Pathlib ka istemal karein
UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True) # Folder banayein agar मौजूद nahi hai

app = Flask(__name__)

# User states ko store karne ke liye ek simple dictionary
# Yeh bot restart hone par reset ho jayegi, jo Render ke liye theek hai
user_states = {}

# --- Telegram Helper Functions ---

def send_telegram(chat_id: int, text: str):
    """Telegram ko text message bhejta hai."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"[send_telegram] Error: {e}")

def send_photo(chat_id: int, image_path: Path):
    """Telegram par photo bhejta hai."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    if not image_path.exists():
        logger.error(f"[send_photo] Image file not found: {image_path}")
        send_telegram(chat_id, "❌ Maaf kijiye, final image banane me problem hui.")
        return
        
    with open(image_path, "rb") as img:
        files = {"photo": img}
        payload = {"chat_id": chat_id}
        try:
            response = requests.post(url, data=payload, files=files)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"[send_photo] Error: {e}")

def get_file_path(file_id: str) -> str | None:
    """Telegram se file ka path haasil karta hai."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile"
    params = {"file_id": file_id}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("result", {}).get("file_path")
    except requests.exceptions.RequestException as e:
        logger.error(f"[get_file_path] Error: {e}")
        return None

# --- Flask Routes ---

@app.route("/", methods=["GET"])
def home():
    return "✅ Affiliate Template Bot Running"

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    """Main webhook jo Telegram se updates leta hai."""
    data = request.json
    if not data or "message" not in data:
        return {"ok": False, "error": "Invalid request"}

    message = data["message"]
    chat_id = message.get("chat", {}).get("id")

    if not chat_id:
        return {"ok": True} # Agar chat_id nahi to ignore karein

    handle_message(chat_id, message)
    return {"ok": True}

# --- Message Handling Logic ---

def handle_message(chat_id: int, message: dict):
    """Aane wale messages ko process karta hai."""
    current_state = user_states.get(str(chat_id), {"stage": None})

    if "text" in message:
        handle_text_message(chat_id, message["text"], current_state)
    elif "photo" in message:
        handle_photo_message(chat_id, message["photo"], current_state)
    else:
        send_telegram(chat_id, "❓ Main sirf text aur photos ko samajhta hoon.")

def handle_text_message(chat_id: int, text: str, current_state: dict):
    """Text messages ke liye logic."""
    stage = current_state.get("stage")

    if text.startswith("/start"):
        templates = list_templates()
        if not templates:
            send_telegram(chat_id, "❌ Koi template nahi mila. 'templates' folder check karein.")
            return
            
        msg = "🖼️ Template choose karein, uska number reply karke:\n"
        for i, t in enumerate(templates, 1):
            msg += f"{i}. {t}\n"
        
        user_states[str(chat_id)] = {"stage": "awaiting_template"}
        send_telegram(chat_id, msg)

    elif stage == "awaiting_template":
        try:
            choice = int(text.strip())
            templates = list_templates()
            if 1 <= choice <= len(templates):
                # Galti yahan theek ki gayi: Sirf filename save karein
                current_state["template"] = templates[choice - 1]
                current_state["stage"] = "awaiting_height"
                user_states[str(chat_id)] = current_state
                send_telegram(chat_id, "📏 Ab product ki max height enter karein (e.g., 1200):")
            else:
                send_telegram(chat_id, "❌ Invalid choice. List me se sahi number enter karein.")
        except (ValueError, IndexError):
            send_telegram(chat_id, "❌ Please ek valid number enter karein.")

    elif stage == "awaiting_height":
        try:
            height = int(text.strip())
            if height > 0:
                current_state["max_height"] = height
                current_state["stage"] = "ready"
                user_states[str(chat_id)] = current_state
                send_telegram(chat_id, "✅ Tayyar! Ab product ki image bhejein.")
            else:
                send_telegram(chat_id, "❌ Height positive number honi chahiye.")
        except ValueError:
            send_telegram(chat_id, "❌ Invalid height. Ek number enter karein jaise 1200.")

    else:
        send_telegram(chat_id, "❓ Samajh nahi aaya. Shuru karne ke liye /start use karein.")

def handle_photo_message(chat_id: int, photo_data: list, current_state: dict):
    """Photo messages ke liye logic."""
    if current_state.get("stage") != "ready":
        send_telegram(chat_id, "❗ Pehle /start command se setup poora karein.")
        return

    # Sabse high-quality photo lein
    file_id = photo_data[-1]["file_id"]
    file_rel_path = get_file_path(file_id)
    if not file_rel_path:
        send_telegram(chat_id, "❌ File download karne me problem hui. Dobara try karein.")
        return

    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_rel_path}"
    
    # Secure filename istemal karein
    local_filename = UPLOAD_FOLDER / secure_filename(file_id + ".jpg")
    output_path = None

    try:
        # Image download karein
        response = requests.get(file_url)
        response.raise_for_status()
        with open(local_filename, "wb") as f:
            f.write(response.content)

        # Image process karein
        output_paths = process_images(
            [local_filename],
            current_state["template"],
            current_state["max_height"]
        )
        
        if output_paths:
            output_path = output_paths[0]
            send_photo(chat_id, output_path)
        else:
            raise ValueError("Image processing failed, returned no path.")

    except Exception as e:
        logger.error(f"[handle_photo_message] Error processing image: {e}")
        send_telegram(chat_id, "⚙️ Image process karte waqt error aaya. Please check logs.")
    finally:
        # Temporary files ko saaf karein
        if local_filename.exists():
            os.remove(local_filename)
        if output_path and output_path.exists():
            os.remove(output_path)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"✅ Starting Flask app on port {port}")
    # debug=False production ke liye behtar hai
    app.run(host="0.0.0.0", port=port, debug=False)
