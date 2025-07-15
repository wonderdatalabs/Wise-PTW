from PIL import Image
import os

# Input and output paths
input_path = "assets/const-bg2.png"
output_path = "assets/const-bg2-resized.png"

try:
    # Open the image
    img = Image.open(input_path)
    
    # Get current dimensions
    orig_width, orig_height = img.size
    print(f"Original dimensions: {orig_width}x{orig_height}")
    
    # Define target dimensions - 16:9 aspect ratio
    target_width = 1920
    target_height = 1080
    
    # Resize image maintaining aspect ratio
    # This will resize and crop to fit the 16:9 aspect ratio perfectly
    img_ratio = orig_width / orig_height
    target_ratio = target_width / target_height
    
    if img_ratio > target_ratio:
        # Image is wider than target ratio - resize based on height and crop width
        resize_height = target_height
        resize_width = int(resize_height * img_ratio)
        img = img.resize((resize_width, resize_height), Image.LANCZOS)
        
        # Crop to target width
        left = (resize_width - target_width) // 2
        right = left + target_width
        img = img.crop((left, 0, right, target_height))
    else:
        # Image is taller than target ratio - resize based on width and crop height
        resize_width = target_width
        resize_height = int(resize_width / img_ratio)
        img = img.resize((resize_width, resize_height), Image.LANCZOS)
        
        # Crop to target height
        top = (resize_height - target_height) // 2
        bottom = top + target_height
        img = img.crop((0, top, target_width, bottom))
    
    # Save the resized image with high quality
    img.save(output_path, "PNG", optimize=True, quality=95)
    print(f"Resized image saved to {output_path}")
    print(f"New dimensions: {img.size[0]}x{img.size[1]}")
    
    # Get file sizes
    orig_size_kb = os.path.getsize(input_path) / 1024
    new_size_kb = os.path.getsize(output_path) / 1024
    print(f"Original size: {orig_size_kb:.2f} KB")
    print(f"New size: {new_size_kb:.2f} KB")
    
except Exception as e:
    print(f"Error: {e}")