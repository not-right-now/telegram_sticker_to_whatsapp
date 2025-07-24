"""
Configuration file for the Telegram to WhatsApp Sticker Converter Bot
"""

# Telegram API Credentials
API_ID = # Your API ID
API_HASH = ""
BOT_TOKEN = ""
BOT_USERNAME = ""

# Required channels for membership verification
REQUIRED_CHANNELS = [] # ["@your_channels_here", "@your_channels_here"]

# Sticker pack constraints
MAX_STICKERS_PER_PACK = 30
MAX_STICKER_SIZE_STATIC = 100 * 1024  # 100KB
MAX_STICKER_SIZE_DYNAMIC = 500*1024 # 500KB

MAX_ICON_SIZE = 50 * 1024      # 50KB
STICKER_DIMENSIONS = (512, 512)
ICON_DIMENSIONS = (96, 96)

# File paths
TEMP_DIR = "temp"
OUTPUT_DIR = "output"

# Messages
START_MESSAGE = """
🎉 Welcome to TG to WA Sticker Converter Bot! 🎉

I can help you convert Telegram sticker packs to WhatsApp compatible .wastickers format!

📋 What I can do:
• Convert Telegram sticker packs to .wastickers format
• Handle both static and animated stickers
• Split large packs (>30 stickers) into multiple files
• Optimize file sizes for WhatsApp compatibility

🚀 How to use:
1. Send me a Telegram sticker pack link (t.me/addstickers/packname)
2. Or forward any sticker from the pack you want to convert
3. Wait for the conversion to complete
4. Download your .wastickers file(s)

📱 To import to WhatsApp:
Use apps like "Sticker Maker" to import the .wastickers files to WhatsApp!

Type /help for more detailed instructions.

⚠️ Note: You must join @your_channels_here to use this bot.
"""

HELP_MESSAGE = """
📖 Help - TG to WA Sticker Converter Bot

🔗 How to convert sticker packs:

Method 1 - Sticker Pack Link:
• Go to any Telegram sticker pack
• Copy the pack link (t.me/addstickers/<packname>)
• Send the link to me

Method 2 - Forward Sticker:
• Forward any sticker from the pack you want
• I'll automatically detect and convert the entire pack

📱 How to import to WhatsApp:
1. Download a "Sticker Maker" app from your app store
2. Open the app and look for "Import" or "Add stickers" option
3. Select the .wastickers file(s) I sent you
4. Follow the app's instructions to add to WhatsApp

📋 Important Notes:
• Large packs (>30 stickers) will be split into multiple files
• Each sticker is optimized for WhatsApp compatibility
• Video/animated stickers are converted perfectly
• You must be a member of @your_channels_here

⏱️ Queue System:
• If multiple users are converting, you'll be added to a queue
• Use the "Check Queue" button to see your position
• Please be patient during busy times

❓ Having issues? Contact @your_group_here for support.
"""

QUEUE_CHECK_MESSAGE = "📊 Queue Status\n\nYour position: {position}\nTotal in queue: {total}\n\n⏰ Estimated wait: {wait_time}"

CHANNEL_JOIN_MESSAGE = """
❌ Access Denied!

To use this bot, you must join these channels first:
• @your_channels_here
• @your_channels_here

After joining both channels, try again!
"""
