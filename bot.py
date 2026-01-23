import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

# Load .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://dracinsubindo.me") # Load from env or default

# Helper function to construct Web App URLs
def get_web_app_url(path=""):
    base = WEB_APP_URL.rstrip('/')
    if path and not path.startswith('/'):
        path = f"/{path}"
    return f"{base}{path}"

async def post_init(application: Application) -> None:
    """Set up bot commands after initialization."""
    await application.bot.set_my_commands([
        ("start", "🎬 Mulai Nonton"),
        ("help", "❓ Bantuan"),
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message with a rich menu to open the web app."""
    user = update.effective_user
    
    # Create a rich menu layout similar to the requested example
    keyboard = [
        # Main generic button
        [InlineKeyboardButton(
            "🎬 Mulai Nonton Film", 
            web_app=WebAppInfo(url=get_web_app_url())
        )],
        # Feature specific buttons (Deep Linking)
        [
            InlineKeyboardButton(" Beli VIP", web_app=WebAppInfo(url=get_web_app_url("/profile#pricing")))
        ],
        [
            InlineKeyboardButton("👤 Profil Saya", web_app=WebAppInfo(url=get_web_app_url("/profile"))),
            # You can add a help link/button here
            # InlineKeyboardButton("❓ Bantuan", url="https://t.me/YourSupportUsername") 
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 <b>Halo, {user.first_name}!</b>\n\n"
        "Selamat datang di <b>DracinLovers</b>.\n"
        "Akses ribuan drama & film Asia subtitle Indonesia terlengkap dan terupdate.\n\n"
        "👇 <b>Pilih menu di bawah untuk memulai:</b>",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))

    # Run the bot until the user presses Ctrl-C
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
