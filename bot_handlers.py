"""
Telegram bot handlers for the TG to WA Sticker Converter Bot
"""

import os
import asyncio
import logging
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from pyrogram import Client
from pyrogram.errors import UserNotParticipant, ChatAdminRequired

from config import *
from utils import *
from queue_manager import queue_manager
from sticker_converter import StickerConverter

logger = logging.getLogger(__name__)

class BotHandlers:
    def __init__(self):
        ensure_directories()
        
        # Initialize Pyrogram client for sticker operations
        self.pyrogram_client = Client(
            "sticker_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN
        )
        
        self.converter = StickerConverter(self.pyrogram_client)
        self.processing_lock = asyncio.Lock()
    
    def _create_channel_join_buttons(self) -> InlineKeyboardMarkup:
        """Dynamically creates the inline keyboard for joining required channels."""
        # Get the list of channels from the config file
        channels = REQUIRED_CHANNELS
        keyboard = []
        # Create a row of buttons, two at a time
        for i in range(0, len(channels), 2):
            row = []
            # First button in the pair
            channel1_username = channels[i]
            # The channel username might contain '@', remove it for the button text
            channel1_name = channel1_username.replace('@', '')
            row.append(InlineKeyboardButton(f"Join {channel1_name}", url=f"https://t.me/{channel1_name}"))

            # Check if there's a second channel for this row
            if i + 1 < len(channels):
                channel2_username = channels[i+1]
                channel2_name = channel2_username.replace('@', '')
                row.append(InlineKeyboardButton(f"Join {channel2_name}", url=f"https://t.me/{channel2_name}"))
            
            keyboard.append(row)
        
        # Add the final "Check Again" button on its own row
        keyboard.append([InlineKeyboardButton("✅ Check Again", callback_data="check_membership")])
        
        return InlineKeyboardMarkup(keyboard)

    async def start_pyrogram(self):
        """Start Pyrogram client"""
        await self.pyrogram_client.start()
    
    async def stop_pyrogram(self):
        """Stop Pyrogram client"""
        await self.pyrogram_client.stop()
    
    async def check_user_membership(self, user_id: int) -> bool:
        """Check if user is member of required channels"""
        try:
            for channel in REQUIRED_CHANNELS:
                try:
                    member = await self.pyrogram_client.get_chat_member(channel, user_id)
                    if member.status in ["left", "kicked"]:
                        return False
                except UserNotParticipant:
                    return False
                except Exception as e:
                    logger.warning(f"Error checking membership for {channel}: {e}")
                    # If we can't check, assume they're not a member
                    return False
            return True
        except Exception as e:
            logger.error(f"Error checking user membership: {e}")
            return False
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        # Check channel membership
        if not await self.check_user_membership(user.id):
            # DYNAMIC KEYBOARD
            reply_markup = self._create_channel_join_buttons()
            
            await update.message.reply_text(
                CHANNEL_JOIN_MESSAGE,
                reply_markup=reply_markup
            )
            return
        
        # Create inline keyboard
        keyboard = [
            [InlineKeyboardButton("📊 Check Queue", callback_data="check_queue")],
            [InlineKeyboardButton("❓ Help", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            START_MESSAGE,
            reply_markup=reply_markup
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        keyboard = [
            [InlineKeyboardButton("📊 Check Queue", callback_data="check_queue")],
            [InlineKeyboardButton("🏠 Back to Start", callback_data="start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            HELP_MESSAGE,
            reply_markup=reply_markup
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages (URLs or stickers)"""
        user = update.effective_user
        
        # Check channel membership
        if not await self.check_user_membership(user.id):
            
            reply_markup = self._create_channel_join_buttons()
            
            await update.message.reply_text(
                CHANNEL_JOIN_MESSAGE,
                reply_markup=reply_markup
            )
            return
        
        # Check if user is already in queue
        if queue_manager.is_user_in_queue(user.id):
            position = queue_manager.get_queue_position(user.id)
            wait_time = estimate_wait_time(position - 1)
            
            keyboard = [[InlineKeyboardButton("📊 Check Queue", callback_data="check_queue")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"⏳ You're already in the queue!\n\n"
                f"Position: {position}\n"
                f"Estimated wait: {wait_time}",
                reply_markup=reply_markup
            )
            return
        
        pack_name = None
        
        # Check if message contains a sticker pack URL
        if update.message.text:
            pack_name = extract_pack_name_from_url(update.message.text)
            if not pack_name:
                await update.message.reply_text(
                    "❌ Invalid sticker pack URL!\n\n"
                    "Please send a valid Telegram sticker pack link (t.me/addstickers/packname) "
                    "or forward a sticker from the pack you want to convert."
                )
                return
        
        # Check if message contains a sticker
        elif update.message.sticker:
            if not update.message.sticker.set_name:
                await update.message.reply_text(
                    "❌ This sticker doesn't belong to a pack!\n\n"
                    "Please forward a sticker from a sticker pack."
                )
                return
            pack_name = update.message.sticker.set_name
        
        else:
            await update.message.reply_text(
                "❌ Unsupported message type!\n\n"
                "Please send:\n"
                "• A Telegram sticker pack link (t.me/addstickers/packname)\n"
                "• Or forward a sticker from the pack you want to convert"
            )
            return
        
        # Add to queue
        user_display_name = get_user_display_name(user)
        position = await queue_manager.add_to_queue(
            user.id, user_display_name, update.effective_chat.id,
            update.message.message_id, pack_name
        )
        
        wait_time = estimate_wait_time(position - 1)
        
        keyboard = [[InlineKeyboardButton("📊 Check Queue", callback_data="check_queue")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Added to conversion queue!\n\n"
            f"📦 Pack: {pack_name}\n"
            f"📍 Position: {position}\n"
            f"⏰ Estimated wait: {wait_time}\n\n"
            f"I'll notify you when the conversion starts!",
            reply_markup=reply_markup
        )
        
        # Start processing if this is the first item
        if position == 1:
            asyncio.create_task(self.process_queue())
    
    async def process_queue(self):
        """Process the conversion queue"""
        async with self.processing_lock:
            while True:
                # Get next item to process
                item = await queue_manager.get_next_item()
                if not item:
                    break
                
                try:
                    # Notify user that processing started
                    await self.pyrogram_client.send_message(
                        item.chat_id,
                        f"🚀 Starting conversion for pack: {item.pack_name}\n\n"
                        f"Please wait while I download and convert the stickers..."
                    )
                    
                    # Get sticker set
                    sticker_set = await self.converter.get_sticker_set(item.pack_name)
                    if not sticker_set:
                        await self.pyrogram_client.send_message(
                            item.chat_id,
                            f"❌ Failed to find sticker pack: {item.pack_name}\n\n"
                            f"Please make sure the pack name is correct and the pack is public."
                        )
                        await queue_manager.complete_processing(item.user_id, False)
                        continue
                    
                    # Notify about pack details
                    # Handle different response structures
                    if hasattr(sticker_set, 'documents'):
                        stickers = sticker_set.documents
                        pack_title = sticker_set.set.title if hasattr(sticker_set, 'set') else "Unknown Pack"
                    elif hasattr(sticker_set, 'stickers'):
                        stickers = sticker_set.stickers
                        pack_title = sticker_set.title if hasattr(sticker_set, 'title') else "Unknown Pack"
                    else:
                        stickers = []
                        pack_title = "Unknown Pack"
                    
                    total_stickers = len(stickers)
                    num_packs = (total_stickers + MAX_STICKERS_PER_PACK - 1) // MAX_STICKERS_PER_PACK
                    
                    await self.pyrogram_client.send_message(
                        item.chat_id,
                        f"📊 Pack Details:\n"
                        f"• Name: {pack_title}\n"
                        f"• Total stickers: {total_stickers}\n"
                        f"• Will create {num_packs} .wastickers file(s)\n\n"
                        f"🔄 Converting stickers..."
                    )
                    
                    # Convert stickers
                    wastickers_files = await self.converter.create_wastickers_pack(
                        sticker_set, item.username
                    )
                    
                    if wastickers_files:
                        # Send converted files
                        await self.pyrogram_client.send_message(
                            item.chat_id,
                            f"✅ Conversion completed successfully!\n\n"
                            f"📁 Generated {len(wastickers_files)} file(s):"
                        )
                        
                        for i, file_path in enumerate(wastickers_files):
                            if os.path.exists(file_path):
                                file_size = format_file_size(os.path.getsize(file_path))
                                caption = f"📦 Part {i+1}/{len(wastickers_files)} - {file_size}"
                                
                                await self.pyrogram_client.send_document(
                                    item.chat_id,
                                    file_path,
                                    caption=caption
                                )
                                
                                # Clean up file
                                os.remove(file_path)
                        
                        # Send instructions
                        await self.pyrogram_client.send_message(
                            item.chat_id,
                            "📱 To import to WhatsApp:\n"
                            "1. Download a 'Sticker Maker' app\n"
                            "2. Import the .wastickers file(s)\n"
                            "3. Add to WhatsApp following the app's instructions\n\n"
                            "🎉 Enjoy your stickers!"
                        )
                        
                        await queue_manager.complete_processing(item.user_id, True)
                    else:
                        await self.pyrogram_client.send_message(
                            item.chat_id,
                            f"❌ Failed to convert sticker pack: {item.pack_name}\n\n"
                            f"This might be due to:\n"
                            f"• Pack contains unsupported formats\n"
                            f"• Network issues\n"
                            f"• Pack is private or restricted\n\n"
                            f"Please try again later."
                        )
                        await queue_manager.complete_processing(item.user_id, False)
                
                except Exception as e:
                    logger.error(f"Error processing queue item: {e}")
                    try:
                        await self.pyrogram_client.send_message(
                            item.chat_id,
                            f"❌ An error occurred during conversion.\n\n"
                            f"Please try again later."
                        )
                    except:
                        pass
                    await queue_manager.complete_processing(item.user_id, False)
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline keyboards"""
        query = update.callback_query
        user = update.effective_user
        
        await query.answer()
        
        if query.data == "check_membership":
            if await self.check_user_membership(user.id):
                keyboard = [
                    [InlineKeyboardButton("📊 Check Queue", callback_data="check_queue")],
                    [InlineKeyboardButton("❓ Help", callback_data="help")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    "✅ Great! You're now a member of both channels.\n\n" + START_MESSAGE,
                    reply_markup=reply_markup
                )
            else:
                await query.edit_message_text(
                    "❌ You still need to join both channels to use this bot.\n\n" + CHANNEL_JOIN_MESSAGE,
                    reply_markup=query.message.reply_markup
                )
        
        elif query.data == "check_queue":
            position = queue_manager.get_queue_position(user.id)
            stats = queue_manager.get_queue_stats()
            
            if position:
                wait_time = estimate_wait_time(position - 1)
                message = QUEUE_CHECK_MESSAGE.format(
                    position=position,
                    total=stats["total_waiting"] + (1 if stats["currently_processing"] else 0),
                    wait_time=wait_time
                )
            else:
                message = (
                    "📊 Queue Status\n\n"
                    f"You're not currently in the queue.\n"
                    f"Total users waiting: {stats['total_waiting']}\n"
                    f"Currently processing: {'Yes' if stats['currently_processing'] else 'No'}"
                )
            
            keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="check_queue")]]
            if position is None:
                keyboard.append([InlineKeyboardButton("🏠 Back to Start", callback_data="start")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, reply_markup=reply_markup)
        
        elif query.data == "help":
            keyboard = [
                [InlineKeyboardButton("📊 Check Queue", callback_data="check_queue")],
                [InlineKeyboardButton("🏠 Back to Start", callback_data="start")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(HELP_MESSAGE, reply_markup=reply_markup)
        
        elif query.data == "start":
            if not await self.check_user_membership(user.id):
                keyboard = [
                    [InlineKeyboardButton("Join @nub_coder_updates", url="https://t.me/nub_coder_updates")],
                    [InlineKeyboardButton("Join @nub_coder_s", url="https://t.me/nub_coder_s")],
                    [InlineKeyboardButton("✅ Check Again", callback_data="check_membership")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(CHANNEL_JOIN_MESSAGE, reply_markup=reply_markup)
            else:
                keyboard = [
                    [InlineKeyboardButton("📊 Check Queue", callback_data="check_queue")],
                    [InlineKeyboardButton("❓ Help", callback_data="help")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(START_MESSAGE, reply_markup=reply_markup)

# Global handlers instance
bot_handlers = BotHandlers()