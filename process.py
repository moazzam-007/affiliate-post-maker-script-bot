import logging
from PIL import Image
from rembg import remove
from io import BytesIO
from datetime import datetime
from pathlib import Path

# Logging setup
logger = logging.getLogger(__name__)

# Pathlib ka istemal karein
TEMPLATES_FOLDER = Path("templates")
OUTPUT_FOLDER = Path("output")

# Ensure folders exist
TEMPLATES_FOLDER.mkdir(exist_ok=True)
OUTPUT_FOLDER.mkdir(exist_ok=True)


def list_templates() -> list[str]:
    """'templates' folder se sabhi image filenames ki list return karta hai."""
    if not TEMPLATES_FOLDER.is_dir():
        logger.warning(f"Template folder not found at: {TEMPLATES_FOLDER}")
        return []
    return sorted([
        f.name for f in TEMPLATES_FOLDER.iterdir()
        if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png"]
    ])


def process_images(
    product_paths: list[Path],
    template_name: str,
    max_height: int
) -> list[Path]:
    """
    Product images ka background remove karke template par paste karta hai.
    Save ki hui images ke paths ki list return karta hai.
    """
    output_paths = []
    
    try:
        # Template ko ek baar load karein
        template_path = TEMPLATES_FOLDER / template_name
        if not template_path.exists():
            logger.error(f"Template file not found: {template_path}")
            return []
            
        template = Image.open(template_path).convert("RGBA")
        W, H = template.size

        # Har product image ke liye loop chalayein
        for product_path in product_paths:
            if not product_path.exists():
                logger.warning(f"Product image not found, skipping: {product_path}")
                continue

            # 1. Background Remove karein
            with open(product_path, "rb") as f:
                product_bytes = remove(f.read())
            product_img = Image.open(BytesIO(product_bytes)).convert("RGBA")

            # 2. Faltu transparent space hatayein (Crop)
            bbox = product_img.getbbox()
            if not bbox:
                logger.warning(f"Could not get bounding box for {product_path}, skipping.")
                continue
            product_img = product_img.crop(bbox)

            # 3. Sahi size me proportional resize karein
            w, h = product_img.size
            if h == 0: continue
            
            scale = max_height / h
            new_width = int(w * scale)
            product_img = product_img.resize((new_width, max_height), Image.LANCZOS)

            # 4. Template ke center me paste karein
            px = (W - new_width) // 2
            py = (H - max_height) // 2
            
            final_image = template.copy()
            final_image.paste(product_img, (px, py), product_img)

            # 5. Final image save karein
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"post_{product_path.stem}_{timestamp}.png"
            output_path = OUTPUT_FOLDER / output_name
            
            final_image.save(output_path, "PNG")
            output_paths.append(output_path)

    except Exception as e:
        logger.error(f"❌ Error during image processing: {e}", exc_info=True)
        return [] # Error aane par khali list return karein

    return output_paths
