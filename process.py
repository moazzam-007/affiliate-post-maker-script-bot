from PIL import Image
from rembg import remove
from io import BytesIO
import os
from datetime import datetime

TEMPLATES_FOLDER = "templates"
OUTPUT_FOLDER = "output"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def list_templates():
    if not os.path.isdir(TEMPLATES_FOLDER):
        return []
    return [
        f for f in os.listdir(TEMPLATES_FOLDER)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

def process_images(product_paths, template_name, max_height):
    output_paths = []
    
    try:
        template_path = os.path.join(TEMPLATES_FOLDER, template_name)
        template = Image.open(template_path).convert("RGBA")
        W, H = template.size

        for product_path in product_paths:
            
            # ############## YAHAN Galti Theek Ki Gayi Hai ##############
            # Bhaari process se pehle image ko resize karein taaki memory bache
            
            with open(product_path, "rb") as f:
                img_data = f.read()

            product_img_for_resize = Image.open(BytesIO(img_data))
            
            # Image ko ek max size (e.g., 1200x1200) me fit karein
            product_img_for_resize.thumbnail((1200, 1200), Image.LANCZOS)
            
            # Resized image ko bytes me convert karein
            resized_img_bytes = BytesIO()
            product_img_for_resize.save(resized_img_bytes, format='PNG')
            resized_img_bytes.seek(0)
            
            # Ab resized image ka background remove karein
            product_bytes = remove(resized_img_bytes.read())
            # ###########################################################

            product_img = Image.open(BytesIO(product_bytes)).convert("RGBA")

            bbox = product_img.getbbox()
            if bbox:
                product_img = product_img.crop(bbox)

            w, h = product_img.size
            if h == 0: continue
            
            scale = max_height / h
            new_width = int(w * scale)
            product_img = product_img.resize((new_width, max_height), Image.LANCZOS)

            px = (W - product_img.width) // 2
            py = (H - product_img.height) // 2
            final = template.copy()
            final.paste(product_img, (px, py), product_img)

            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            base_name = os.path.splitext(os.path.basename(product_path))[0]
            output_name = f"post_{base_name}_{timestamp}.png"
            output_path = os.path.join(OUTPUT_FOLDER, output_name)
            final.save(output_path)
            
            output_paths.append(output_path)

        return output_paths

    except Exception as e:
        print(f"❌ Error processing images: {e}")
        return []
