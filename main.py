"""
Main entry point for the Telegram to WhatsApp Sticker Converter Bot
"""

import logging
import asyncio
import signal
import sys
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from config import BOT_TOKEN
from bot_handlers import BotHandlers

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

class StickerBot:
    def __init__(self):
        self.application = None
        self.running = False
        self.bot_handlers = BotHandlers()
    
    async def start_bot(self):
        """Initialize and start the bot"""
        try:
            # Create application
            self.application = Application.builder().token(BOT_TOKEN).build()
            
            # Start Pyrogram client
            await self.bot_handlers.start_pyrogram()
            logger.info("Pyrogram client started")
            
            # Add command handlers with a filter for private chats only
            self.application.add_handler(CommandHandler(
                "start", 
                self.bot_handlers.start_command, 
                filters=filters.ChatType.PRIVATE
            ))
            self.application.add_handler(CommandHandler(
                "help", 
                self.bot_handlers.help_command, 
                filters=filters.ChatType.PRIVATE
            ))
            
            # Add message handler with a combined filter for content AND private chat
            self.application.add_handler(MessageHandler(
                (filters.TEXT | filters.Sticker.ALL) & filters.ChatType.PRIVATE, 
                self.bot_handlers.handle_message
            ))
            
            # The CallbackQueryHandler does not need a filter, as the buttons 
            # that trigger it will now only exist in private chats.
            self.application.add_handler(CallbackQueryHandler(self.bot_handlers.handle_callback_query))
            
            # Start the bot
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            self.running = True
            logger.info("Bot started successfully!")
            
            # Keep the bot running
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise
    
    async def stop_bot(self):
        """Stop the bot gracefully"""
        logger.info("Stopping bot...")
        self.running = False
        
        try:
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            
            # Stop Pyrogram client
            await self.bot_handlers.stop_pyrogram()
            logger.info("Bot stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    # This will be handled by the main loop
    sys.exit(0)

async def main():
    """Main function"""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    bot = StickerBot()
    
    try:
        await bot.start_bot()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        await bot.stop_bot()

if __name__ == "__main__":
    # Check if FFmpeg is available
    # import shutil
    # if not shutil.which("ffmpeg"):
    #     logger.error("FFmpeg not found! Please install FFmpeg to handle video stickers.")
    #     logger.error("On Ubuntu/Debian: sudo apt-get install ffmpeg")
    #     logger.error("On CentOS/RHEL: sudo dnf install ffmpeg")
    #     sys.exit(1)
    
    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown complete")
