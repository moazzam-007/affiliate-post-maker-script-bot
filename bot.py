# affiliate_post_bot.py
import os
from flask import Flask, request
from datetime import datetime
from PIL import Image
from rembg import remove
from io import BytesIO
import requests

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
MAX_HEIGHT = int(os.environ.get("MAX_HEIGHT", "1100"))
TEMPLATE_PATH = "template.png"
OUTPUT_FOLDER = "output"
W, H = Image.open(TEMPLATE_PATH).size

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def send_telegram_photo(chat_id, image_bytes):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    files = {"photo": image_bytes}
    data = {"chat_id": chat_id}
    requests.post(url, data=data, files=files)

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.json
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    photo = message.get("photo", [])

    if not photo:
        send_message(chat_id, "❌ Please send a product image.")
        return {"ok": True}

    # Get highest quality photo
    file_id = photo[-1]["file_id"]
    file_info = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}").json()
    file_path = file_info["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    image_data = requests.get(file_url).content
    processed_img = process_image(image_data)

    # Save for record (optional)
    filename = f"post_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    output_path = os.path.join(OUTPUT_FOLDER, filename)
    processed_img.save(output_path)

    # Send back
    img_bytes = BytesIO()
    processed_img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    send_telegram_photo(chat_id, img_bytes)
    
    return {"ok": True}

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text})

def process_image(img_bytes):
    # Load and remove BG
    no_bg_bytes = remove(img_bytes)
    product_img = Image.open(BytesIO(no_bg_bytes)).convert("RGBA")

    # Crop transparent
    bbox = product_img.getbbox()
    if bbox:
        product_img = product_img.crop(bbox)

    # Resize
    w, h = product_img.size
    scale = MAX_HEIGHT / h
    new_w = int(w * scale)
    product_img = product_img.resize((new_w, MAX_HEIGHT), Image.LANCZOS)

    # Paste to center
    template = Image.open(TEMPLATE_PATH).convert("RGBA")
    px = (W - product_img.width) // 2
    py = (H - product_img.height) // 2
    template.paste(product_img, (px, py), product_img)

    return template

@app.route("/")
def home():
    return "✅ Affiliate Post Bot Running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
