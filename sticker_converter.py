"""
Sticker conversion functionality for Telegram to WhatsApp converter
"""

import os
import io
import zipfile
import tempfile
import subprocess
import asyncio
from typing import List, Tuple, Optional
from PIL import Image
import aiohttp
import logging
import asyncio
from pyrogram import Client
from pyrogram.types import Sticker
import pyrogram.raw.functions.messages
import pyrogram.raw.functions.upload
import pyrogram.raw.types
from tgs_to_webp import convert_tgs_to_webp
from video_to_webp import convert_video_to_webp

from config import *
from utils import *

logger = logging.getLogger(__name__)

class StickerConverter:
    def __init__(self, client: Client):
        self.client = client
    
    async def get_sticker_set(self, pack_name: str):
        """Get sticker set from Telegram"""
        try:
            # Use invoke method to call getStickerSet directly
            sticker_set = await self.client.invoke(
                pyrogram.raw.functions.messages.GetStickerSet(
                    stickerset=pyrogram.raw.types.InputStickerSetShortName(short_name=pack_name),
                    hash=0
                )
            )
            # Debug logging to understand the structure
            logger.info(f"Retrieved sticker set structure: {type(sticker_set)}")
            logger.info(f"Available attributes: {[attr for attr in dir(sticker_set) if not attr.startswith('_')]}")
            return sticker_set
        except Exception as e:
            logger.error(f"Failed to get sticker set {pack_name}: {e}")
            return None
    
    async def get_sticker_set_from_sticker(self, sticker: Sticker):
        """Get sticker set from a sticker object"""
        try:
            if sticker.set_name:
                return await self.get_sticker_set(sticker.set_name)
        except Exception as e:
            logger.error(f"Failed to get sticker set from sticker: {e}")
        return None
    
    async def download_sticker(self, sticker, temp_dir: str) -> Optional[str]:
        """Download a single sticker file"""
        try:
            # For raw Document objects, use the document directly with invoke
            if hasattr(sticker, 'id') and hasattr(sticker, 'access_hash'):
                # Use the document's file extension based on MIME type
                extension = ""
                if hasattr(sticker, 'mime_type'):
                    if sticker.mime_type == 'image/webp':
                        extension = ".webp"
                    elif sticker.mime_type == 'video/webm':
                        extension = ".webm"
                    elif sticker.mime_type == 'application/x-tgsticker':
                        extension = ".tgs"
                    else:
                        # Try to get from attributes
                        if hasattr(sticker, 'attributes'):
                            for attr in sticker.attributes:
                                if hasattr(attr, 'file_name') and attr.file_name:
                                    extension = "." + attr.file_name.split('.')[-1]
                                    break
                
                # Create temp file path
                file_path = f"{temp_dir}/temp_sticker{extension}"
                
                # Download using invoke with uploadGetFile
                await self._download_document(sticker, file_path)
                return file_path
            else:
                # Fallback for high-level objects
                file_path = await self.client.download_media(
                    sticker,
                    file_name=f"{temp_dir}/temp_sticker"
                )
                return file_path
        except Exception as e:
            logger.error(f"Failed to download sticker: {e}")
            logger.error(f"Sticker object type: {type(sticker)}")
            if hasattr(sticker, 'id'):
                logger.error(f"Document ID: {sticker.id}")
            if hasattr(sticker, 'mime_type'):
                logger.error(f"MIME type: {sticker.mime_type}")
            return None
    
    async def _download_document(self, document, file_path: str):
        """Download a document using raw API calls"""
        try:
            # Use getFile to download the document
            file_location = pyrogram.raw.types.InputDocumentFileLocation(
                id=document.id,
                access_hash=document.access_hash,
                file_reference=getattr(document, 'file_reference', b''),
                thumb_size=""
            )
            
            # Download in chunks
            offset = 0
            limit = 1024 * 1024  # 1MB chunks
            
            with open(file_path, 'wb') as f:
                while True:
                    r = await self.client.invoke(
                        pyrogram.raw.functions.upload.GetFile(
                            location=file_location,
                            offset=offset,
                            limit=limit
                        )
                    )
                    
                    if not r.bytes:
                        break
                        
                    f.write(r.bytes)
                    offset += len(r.bytes)
                    
                    if len(r.bytes) < limit:
                        break
            
            logger.info(f"Successfully downloaded document to {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to download document: {e}")
            raise
    
    async def convert_to_webp(self, input_path: str, output_path: str) -> bool:
        """Convert various sticker formats to WebP"""
        try:
            file_ext = os.path.splitext(input_path)[1].lower()
            
            if file_ext == '.tgs':
                # Animated Telegram sticker - convert using tgs_to_webp module
                return await self._convert_tgs_to_webp(input_path, output_path)
            if file_ext in ['.webm', '.mp4', '.gif', '.mov', '.mkv']: # A list of all supported video types 
                # Video files - convert using video_to_webp module
                return await self._convert_video_to_webp(input_path, output_path)
            else:
                # Static image - convert using PIL
                return await self._convert_image_to_webp(input_path, output_path)
                
        except Exception as e:
            logger.error(f"Failed to convert {input_path} to WebP: {e}")
            return False
    
    async def _convert_tgs_to_webp(self, input_path: str, output_path: str) -> bool:
        """Convert TGS (Telegram animated sticker) to animated WebP using the new module."""
        try:
            # Run the synchronous conversion function in a separate thread
            # to avoid blocking the asyncio event loop.
            success = await asyncio.to_thread(
                convert_tgs_to_webp,
                tgs_path=input_path,
                webp_path=output_path,
                quality=80, 
                preserve_timing=True
            )
            return success
        except Exception as e:
            logger.error(f"Error converting TGS with new module: {e}")
            return False
    
    async def _convert_video_to_webp(self, input_path: str, output_path: str) -> bool:
        """
        Converts a video file to an animated WebP using the video_to_webp module.
        """
        try:
            # Run the synchronous conversion function in a separate thread
            # to avoid blocking the bot's event loop.
            success = await asyncio.to_thread(
                convert_video_to_webp,
                video_path=input_path,
                webp_path=output_path,
                quality=80,
                preserve_timing=True 
            )
            return success
        except Exception as e:
            logger.error(f"Error converting video with module: {e}")
            return False
    
    async def _convert_image_to_webp(self, input_path: str, output_path: str) -> bool:
        """Convert static image to WebP"""
        try:
            with Image.open(input_path) as img:
                # Convert to RGBA
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                # Resize maintaining aspect ratio
                img.thumbnail(STICKER_DIMENSIONS, Image.Resampling.LANCZOS)
                
                # Create new image with white background
                new_img = Image.new('RGBA', STICKER_DIMENSIONS, (255, 255, 255, 0))
                
                # Center the image
                x = (STICKER_DIMENSIONS[0] - img.width) // 2
                y = (STICKER_DIMENSIONS[1] - img.height) // 2
                new_img.paste(img, (x, y), img)
                
                # Save as WebP with optimization
                new_img.save(output_path, format='WEBP', quality=80, optimize=True)
                
            return os.path.exists(output_path)
            
        except Exception as e:
            logger.error(f"Error converting image: {e}")
            return False
    
    async def create_wastickers_pack(self, sticker_set, author_name: str, 
                                   pack_number: int = 1) -> List[str]:
        """Create .wastickers file(s) from sticker set"""
        wastickers_files = []
        temp_dir = create_temp_directory()
        
        try:
            # Handle raw API response structure
            if hasattr(sticker_set, 'documents'):
                stickers = sticker_set.documents
            else:
                stickers = sticker_set.stickers if hasattr(sticker_set, 'stickers') else []
            total_stickers = len(stickers)
            
            # Calculate number of packs needed
            num_packs = (total_stickers + MAX_STICKERS_PER_PACK - 1) // MAX_STICKERS_PER_PACK
            
            for pack_idx in range(num_packs):
                start_idx = pack_idx * MAX_STICKERS_PER_PACK
                end_idx = min(start_idx + MAX_STICKERS_PER_PACK, total_stickers)
                pack_stickers = stickers[start_idx:end_idx]
                
                # Get pack title from the correct structure
                if hasattr(sticker_set, 'set') and hasattr(sticker_set.set, 'title'):
                    pack_title = sticker_set.set.title
                elif hasattr(sticker_set, 'title'):
                    pack_title = sticker_set.title
                else:
                    pack_title = "Sticker Pack"
                    
                if num_packs > 1:
                    pack_title += f" {pack_idx + 1}"
                
                wastickers_file = await self._create_single_wastickers_pack(
                    pack_stickers, pack_title, author_name, temp_dir, pack_idx + 1
                )
                
                if wastickers_file:
                    wastickers_files.append(wastickers_file)
            
            return wastickers_files
            
        except Exception as e:
            logger.error(f"Failed to create wastickers pack: {e}")
            return []
        finally:
            cleanup_temp_directory(temp_dir)
    
    async def _create_single_wastickers_pack(self, stickers: List[Sticker], title: str, 
                                           author_name: str, temp_dir: str, pack_number: int) -> Optional[str]:
        """Create a single .wastickers file"""
        pack_temp_dir = os.path.join(temp_dir, f"pack_{pack_number}")
        os.makedirs(pack_temp_dir, exist_ok=True)
        
        try:
            converted_stickers = []
            
            # Convert each sticker
            for i, sticker in enumerate(stickers):
                sticker_file = await self.download_sticker(sticker, pack_temp_dir)
                if not sticker_file:
                    continue

                # Check the original file type to see if it's animated
                original_ext = os.path.splitext(sticker_file)[1].lower()
                is_animated = original_ext in ['.tgs', '.webm', '.mp4', '.gif', '.mov', '.mkv']

                # Convert to WebP
                webp_path = os.path.join(pack_temp_dir, f"{i+1:02d}.webp")
                success = await self.convert_to_webp(sticker_file, webp_path)
                
                if success:
                    # Optimize file size
                    # Only optimize static images. Animated ones are already optimized.
                    if not is_animated:
                        with open(webp_path, 'rb') as f:
                            original_data = f.read()
                        
                        optimized_data = optimize_image_size(original_data, MAX_STICKER_SIZE_STATIC, STICKER_DIMENSIONS)
                        
                        with open(webp_path, 'wb') as f:
                            f.write(optimized_data)
                    
                    # Add a check for oversized animated stickers
                    if not is_animated:
                        if os.path.getsize(webp_path) > MAX_STICKER_SIZE_STATIC:
                            logger.warning(f"Sticker {webp_path} is larger than {MAX_STICKER_SIZE_STATIC} bytes and might be rejected by WhatsApp.")
                    else:
                        if os.path.getsize(webp_path) > MAX_STICKER_SIZE_DYNAMIC:
                            logger.warning(f"Sticker {webp_path} is larger than {MAX_STICKER_SIZE_DYNAMIC} bytes and might be rejected by WhatsApp.")
                    
                    converted_stickers.append(webp_path)
                
                # Clean up original file
                if os.path.exists(sticker_file):
                    os.remove(sticker_file)
            
            if not converted_stickers:
                logger.error("No stickers were successfully converted")
                return None
            
            # Create icon from first sticker
            icon_path = os.path.join(pack_temp_dir, "icon.png")
            await self._create_icon(converted_stickers[0], icon_path)
            
            # Create metadata files
            await self._create_metadata_files(pack_temp_dir, title, author_name)
            
            # Create .wastickers archive
            output_file = os.path.join(OUTPUT_DIR, f"{sanitize_filename(title)}.wastickers")
            await self._create_wastickers_archive(pack_temp_dir, output_file)
            
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to create single wastickers pack: {e}")
            return None
    
    async def _create_icon(self, first_sticker_path: str, icon_path: str):
        """Create icon.png from first sticker"""
        try:
            with Image.open(first_sticker_path) as img:
                # Convert to RGB (remove alpha for PNG)
                if img.mode == 'RGBA':
                    # Create white background
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize to icon dimensions
                img = img.resize(ICON_DIMENSIONS, Image.Resampling.LANCZOS)
                
                # Save as PNG with optimization
                img.save(icon_path, format='PNG', optimize=True)
                
                # Check file size and optimize if needed
                if os.path.getsize(icon_path) > MAX_ICON_SIZE:
                    # Re-save with lower quality
                    img.save(icon_path, format='PNG', optimize=True, quality=70)
                    
        except Exception as e:
            logger.error(f"Failed to create icon: {e}")
    
    async def _create_metadata_files(self, pack_dir: str, title: str, author_name: str):
        """Create author.txt and title.txt files"""
        try:
            # Create author.txt
            author_path = os.path.join(pack_dir, "author.txt")
            with open(author_path, 'w', encoding='utf-8') as f:
                f.write(author_name)
            
            # Create title.txt
            title_path = os.path.join(pack_dir, "title.txt")
            with open(title_path, 'w', encoding='utf-8') as f:
                f.write(title)
                
        except Exception as e:
            logger.error(f"Failed to create metadata files: {e}")
    
    async def _create_wastickers_archive(self, pack_dir: str, output_file: str):
        """Create the final .wastickers archive"""
        try:
            with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(pack_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_name = os.path.relpath(file_path, pack_dir)
                        zf.write(file_path, arc_name)
                        
        except Exception as e:
            logger.error(f"Failed to create wastickers archive: {e}")
            raise