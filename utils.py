"""
Utility functions for the Telegram to WhatsApp Sticker Converter Bot
"""

import os
import re
import tempfile
import shutil
from typing import Optional, Tuple
from PIL import Image
import io

def ensure_directories():
    """Create necessary directories if they don't exist"""
    from config import TEMP_DIR, OUTPUT_DIR
    
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def extract_pack_name_from_url(url: str) -> Optional[str]:
    """Extract sticker pack name from Telegram URL"""
    patterns = [
        r't\.me/addstickers/(.+)',
        r'telegram\.me/addstickers/(.+)',
        r'addstickers/(.+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def optimize_image_size(image_data: bytes, max_size: int, dimensions: Tuple[int, int]) -> bytes:
    """Optimize image to meet size constraints while maintaining quality"""
    img = Image.open(io.BytesIO(image_data))
    
    # Convert to RGBA if not already
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Resize to target dimensions
    img = img.resize(dimensions, Image.Resampling.LANCZOS)
    
    # Try different quality settings to meet size constraint
    for quality in range(95, 10, -5):
        output = io.BytesIO()
        img.save(output, format='WEBP', quality=quality, optimize=True)
        
        if output.tell() <= max_size:
            return output.getvalue()
    
    # If still too large, try with minimal quality
    output = io.BytesIO()
    img.save(output, format='WEBP', quality=10, optimize=True)
    return output.getvalue()

def create_temp_directory() -> str:
    """Create a temporary directory for processing"""
    from config import TEMP_DIR
    return tempfile.mkdtemp(dir=TEMP_DIR)

def cleanup_temp_directory(temp_dir: str):
    """Clean up temporary directory"""
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file system usage"""
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove leading/trailing spaces and dots
    filename = filename.strip(' .')
    # Limit length
    if len(filename) > 50:
        filename = filename[:50]
    
    return filename or "sticker_pack"

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

def get_user_display_name(user) -> str:
    """Get user display name with fallback"""
    from config import BOT_USERNAME
    
    if user.username:
        return f"@{user.username}"
    elif user.first_name:
        return user.first_name
    else:
        return BOT_USERNAME

def is_valid_sticker_url(url: str) -> bool:
    """Check if URL is a valid Telegram sticker pack URL"""
    return extract_pack_name_from_url(url) is not None

def estimate_wait_time(queue_position: int) -> str:
    """Estimate wait time based on queue position"""
    # Assume average 2-3 minutes per conversion
    minutes = queue_position * 2.5
    
    if minutes < 1:
        return "Less than 1 minute"
    elif minutes < 60:
        return f"{int(minutes)} minutes"
    else:
        hours = minutes / 60
        return f"{hours:.1f} hours"
