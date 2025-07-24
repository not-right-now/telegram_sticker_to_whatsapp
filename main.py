"""
Main entry point for the Telegram to WhatsApp Sticker Converter Bot (Telethon Version)
"""

import logging
import asyncio
from telethon import TelegramClient

from config import API_ID, API_HASH, BOT_TOKEN
from bot_handlers import BotHandlers

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

async def main():
    """
    Initializes the Telethon client, registers handlers, and runs the bot.
    """
    # We use a session name for the bot so it can remember its state.
    # The session file will be created in the same directory.
    client = TelegramClient('bot_session', API_ID, API_HASH)

    # Initialize handlers with the client instance
    handlers = BotHandlers(client)
    # Register all event handlers
    handlers.register_handlers()

    logger.info("Starting bot...")
    try:
        # Start the client with the bot token
        await client.start(bot_token=BOT_TOKEN)
        logger.info("Bot started successfully!")

        # The bot will run until you press Ctrl+C
        await client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Failed to start or run the bot: {e}")
    finally:
        if client.is_connected():
            await client.disconnect()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    try:
        # Run the main async function
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested by user.")

