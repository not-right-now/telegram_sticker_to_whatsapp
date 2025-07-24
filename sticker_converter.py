"""
Sticker conversion functionality for Telegram to WhatsApp converter (Telethon Version)
"""

import os
import zipfile
import asyncio
from typing import List, Optional, Any
from PIL import Image
import logging

from telethon import TelegramClient
from telethon.tl.functions.messages import GetStickerSetRequest
# Corrected imports: Using the concrete, real type
from telethon.tl.types import InputStickerSetShortName, InputStickerSetID, Document
from telethon.errors.rpcerrorlist import StickersetInvalidError

from tgs_to_webp import convert_tgs_to_webp
from video_to_webp import convert_video_to_webp
from config import *
from utils import *

logger = logging.getLogger(__name__)

class StickerConverter:
    def __init__(self, client: TelegramClient):
        self.client = client
    
    async def get_sticker_set(self, pack_input: Any):
        """
        Get sticker set from Telegram using either a short name (str) 
        or a concrete InputStickerSet type (like InputStickerSetID).
        """
        try:
            input_set = None
            if isinstance(pack_input, str):
                # If we get a string, we assume it's a short_name
                input_set = InputStickerSetShortName(short_name=pack_input)
            elif isinstance(pack_input, (InputStickerSetID, InputStickerSetShortName)):
                # If we get a valid InputStickerSet object, use it directly
                input_set = pack_input
            else:
                logger.error(f"Invalid type provided for sticker pack: {type(pack_input)}")
                return None

            sticker_set = await self.client(GetStickerSetRequest(
                stickerset=input_set,
                hash=0
            ))
            return sticker_set
        except StickersetInvalidError:
            logger.error(f"The sticker set '{pack_input}' is invalid or does not exist.")
            return None
        except Exception as e:
            logger.error(f"Failed to get sticker set {pack_input}: {e}")
            return None
    
    async def download_sticker(self, sticker: Document, temp_dir: str) -> Optional[str]:
        """
        Download a single sticker file using Telethon.
        Telethon's download_media automatically handles FILE_MIGRATE_X errors.
        """
        try:
            file_path = os.path.join(temp_dir, f"sticker_{sticker.id}")
            downloaded_path = await self.client.download_media(sticker, file=file_path)
            logger.info(f"Successfully downloaded sticker {sticker.id} to {downloaded_path}")
            return downloaded_path
        except Exception as e:
            logger.error(f"Failed to download sticker {sticker.id}: {e}")
            return None

    async def convert_to_webp(self, input_path: str, output_path: str) -> bool:
        """Convert various sticker formats to WebP."""
        try:
            file_ext = os.path.splitext(input_path)[1].lower() if input_path else ''
            
            if file_ext == '.tgs':
                return await asyncio.to_thread(convert_tgs_to_webp, input_path, output_path, quality=40, preserve_timing=True)
            elif file_ext in ['.webm', '.mp4', '.gif', '.mov', '.mkv']:
                return await asyncio.to_thread(convert_video_to_webp, input_path, output_path, quality=80, preserve_timing=True)
            else: # Static image
                with Image.open(input_path) as img:
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    img.thumbnail(STICKER_DIMENSIONS, Image.Resampling.LANCZOS)
                    new_img = Image.new('RGBA', STICKER_DIMENSIONS, (0, 0, 0, 0))
                    x = (STICKER_DIMENSIONS[0] - img.width) // 2
                    y = (STICKER_DIMENSIONS[1] - img.height) // 2
                    new_img.paste(img, (x, y), img)
                    new_img.save(output_path, 'WEBP', quality=80)
                return True
        except Exception as e:
            logger.error(f"Failed to convert {input_path} to WebP: {e}")
            return False
    
    async def create_wastickers_pack(self, sticker_set, author_name: str) -> List[str]:
        """Create .wastickers file(s) from a sticker set."""
        wastickers_files = []
        temp_dir = create_temp_directory()
        
        try:
            stickers = sticker_set.documents
            total_stickers = len(stickers)
            num_packs = (total_stickers + MAX_STICKERS_PER_PACK - 1) // MAX_STICKERS_PER_PACK
            
            for pack_idx in range(num_packs):
                start_idx = pack_idx * MAX_STICKERS_PER_PACK
                end_idx = min(start_idx + MAX_STICKERS_PER_PACK, total_stickers)
                pack_stickers = stickers[start_idx:end_idx]
                
                pack_title = sticker_set.set.title
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

    async def _create_single_wastickers_pack(self, stickers: List[Document], title: str, 
                                           author_name: str, temp_dir: str, pack_number: int) -> Optional[str]:
        """Create a single .wastickers file."""
        pack_temp_dir = os.path.join(temp_dir, f"pack_{pack_number}")
        os.makedirs(pack_temp_dir, exist_ok=True)
        
        try:
            converted_stickers = []
            for i, sticker in enumerate(stickers):
                sticker_file = await self.download_sticker(sticker, pack_temp_dir)
                if not sticker_file:
                    continue

                webp_path = os.path.join(pack_temp_dir, f"{i+1:02d}.webp")
                
                if await self.convert_to_webp(sticker_file, webp_path):
                    converted_stickers.append(webp_path)
                
                if os.path.exists(sticker_file):
                    os.remove(sticker_file)
            
            if not converted_stickers:
                return None
            
            await self._create_icon(converted_stickers[0], os.path.join(pack_temp_dir, "icon.png"))
            await self._create_metadata_files(pack_temp_dir, title, author_name)
            
            output_file = os.path.join(OUTPUT_DIR, f"{sanitize_filename(title)}.wastickers")
            await self._create_wastickers_archive(pack_temp_dir, output_file)
            return output_file
        except Exception as e:
            logger.error(f"Failed to create single wastickers pack: {e}")
            return None

    async def _create_icon(self, first_sticker_path: str, icon_path: str):
        """Create icon.png from the first sticker."""
        try:
            with Image.open(first_sticker_path) as img:
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                img.thumbnail(ICON_DIMENSIONS, Image.Resampling.LANCZOS)
                img.save(icon_path, 'PNG')
        except Exception as e:
            logger.error(f"Failed to create icon: {e}")

    async def _create_metadata_files(self, pack_dir: str, title: str, author_name: str):
        """Create author.txt and title.txt files."""
        with open(os.path.join(pack_dir, "author.txt"), 'w', encoding='utf-8') as f:
            f.write(author_name)
        with open(os.path.join(pack_dir, "title.txt"), 'w', encoding='utf-8') as f:
            f.write(title)

    async def _create_wastickers_archive(self, pack_dir: str, output_file: str):
        """Create the final .wastickers archive."""
        with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(pack_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, pack_dir)
                    zf.write(file_path, arc_name)
