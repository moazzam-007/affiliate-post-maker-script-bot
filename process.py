from PIL import Image 
from rembg import remove 
from io import BytesIO 
import os 
from datetime import datetime 

TEMPLATES_FOLDER = "templates" 
OUTPUT_FOLDER = "output" 

# Ensure output folder exists 
os.makedirs(OUTPUT_FOLDER, exist_ok=True) 


# NAAM BADAL DIYA GAYA: load_templates -> list_templates 
def list_templates(): 
    """Return list of template filenames (jpg and png).""" 
    if not os.path.isdir(TEMPLATES_FOLDER): 
        return [] 
    return [ 
        f for f in os.listdir(TEMPLATES_FOLDER) 
        if f.lower().endswith((".jpg", ".jpeg", ".png")) 
    ] 


# FUNCTION UPDATE KIYA GAYA: Ab multiple images ki list leta hai 
def process_images(product_paths, template_name, max_height): 
    """ 
    Removes background from a list of product images, pastes them on the 
    selected template, and saves the final images. 
    Returns a list of saved paths. 
    """ 
    output_paths = [] 
    
    try: 
        # Load template just once 
        template_path = os.path.join(TEMPLATES_FOLDER, template_name) 
        template = Image.open(template_path).convert("RGBA") 
        W, H = template.size 

        # Har product image ke liye loop chalayein 
        for product_path in product_paths: 
            # Remove background 
            with open(product_path, "rb") as f: 
                product_bytes = remove(f.read()) 
            product_img = Image.open(BytesIO(product_bytes)).convert("RGBA") 

            # Tight crop (removes empty transparent areas) 
            bbox = product_img.getbbox() 
            if bbox: 
                product_img = product_img.crop(bbox) 

            # Resize proportionally by height 
            w, h = product_img.size 
            if h == 0: continue # Agar image ki height 0 hai to skip karein 
            
            scale = max_height / h 
            new_width = int(w * scale) 
            product_img = product_img.resize((new_width, max_height), Image.LANCZOS) 

            # Center on template 
            px = (W - product_img.width) // 2 
            py = (H - product_img.height) // 2 
            final = template.copy() 
            final.paste(product_img, (px, py), product_img) 

            # Save final image 
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f") 
            base_name = os.path.splitext(os.path.basename(product_path))[0] 
            output_name = f"post_{base_name}_{timestamp}.png" 
            output_path = os.path.join(OUTPUT_FOLDER, output_name) 
            final.save(output_path) 
            
            output_paths.append(output_path) 

        return output_paths 

    except Exception as e: 
        print(f"❌ Error processing images: {e}") 
        return [] # Khali list return karein agar error aaye
