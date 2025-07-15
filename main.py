import os
import logging
import json
from io import BytesIO
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler
)

# Audio processing imports
import youtube_dl
import ffmpeg
import requests

# Load environment variables
load_dotenv()
TOKEN = os.getenv('TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global variables
user_messages = {}
banned_users = set()
music_queue = []
group_settings = {}
welcome_messages = {}

# Conversation states
WAITING_WELCOME = 1

# ====================== CORE FUNCTIONS ======================

def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    update.message.reply_text(
        f"🎵 Hello {user.first_name}! I'm Muskan Music Bot!\n"
        "Use /help to see available commands."
    )

def help(update: Update, context: CallbackContext):
    help_text = """
    🎶 Available Commands:
    
    🔊 Music:
    /play <song> - Play a song (192kbps HQ)
    /search <song> - Search for songs
    /queue - Show current playlist
    
    👥 Group Management:
    /setup - Initialize bot in group
    /settings - Configure group
    /welcome <msg> - Set welcome message
    
    💬 Chat:
    /admin <message> - Contact admin
    /reply <user_id> <msg> - Reply to user (Admin only)
    
    ⚙️ Admin:
    /ban <user_id> - Ban user
    /unban <user_id> - Unban user
    /broadcast <msg> - Send to all users
    """
    update.message.reply_text(help_text)

# ====================== IMPROVED MUSIC FUNCTIONS ======================

def play_music(update: Update, context: CallbackContext):
    # Check if music is enabled in group
    chat_id = update.message.chat.id
    if chat_id in group_settings and not group_settings[chat_id]['music_enabled']:
        update.message.reply_text("❌ Music is disabled in this group")
        return
    
    if not context.args:
        update.message.reply_text("Please specify a song after /play")
        return
    
    query = ' '.join(context.args)
    try:
        # HQ audio settings
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'extractaudio': True,
            'audioformat': 'mp3'
        }
        
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
            audio_url = info['url']
            title = info['title']
            duration = info['duration']
            
            if duration > 900:  # 15 minute limit
                update.message.reply_text("❌ Videos longer than 15 minutes aren't supported")
                return
        
        # Add to queue with metadata
        music_queue.append({
            'url': audio_url,
            'title': title,
            'requested_by': update.message.from_user.id,
            'chat_id': chat_id
        })
        
        update.message.reply_text(f"🎧 Added to queue: {title}")
        
        if len(music_queue) == 1:
            send_music(update, context)
            
    except Exception as e:
        update.message.reply_text(f"❌ Error: {str(e)}")
        logger.error(f"Music error: {str(e)}")

def send_music(update: Update, context: CallbackContext):
    if not music_queue:
        return
        
    current_song = music_queue[0]
    try:
        # Stream HQ audio
        audio_data = BytesIO(requests.get(current_song['url']).content)
        audio_data.name = 'song.mp3'
        
        context.bot.send_audio(
            chat_id=current_song['chat_id'],
            audio=audio_data,
            title=current_song['title'],
            performer=f"Requested by {user_messages.get(current_song['requested_by'], {}).get('username', 'Anonymous')}",
            parse_mode='HTML'
        )
        
        music_queue.pop(0)
        if music_queue:
            send_music(update, context)
            
    except Exception as e:
        update.message.reply_text(f"❌ Playback error: {str(e)}")

# ====================== GROUP MANAGEMENT ======================

def setup_group(update: Update, context: CallbackContext):
    chat_id = update.message.chat.id
    if chat_id not in group_settings:
        group_settings[chat_id] = {
            'admins': [update.message.from_user.id],
            'music_enabled': True,
            'welcome_enabled': False
        }
        save_group_data()
        update.message.reply_text("✅ Group setup complete! Use /settings to configure")
    else:
        update.message.reply_text("ℹ️ Group already setup")

def group_settings_menu(update: Update, context: CallbackContext):
    chat_id = update.message.chat.id
    if chat_id not in group_settings:
        update.message.reply_text("❌ Group not setup. Use /setup first")
        return
    
    keyboard = [
        [InlineKeyboardButton("Toggle Music", callback_data=f'toggle_music_{chat_id}')],
        [InlineKeyboardButton("Set Welcome", callback_data=f'set_welcome_{chat_id}')],
        [InlineKeyboardButton("Admin List", callback_data=f'admin_list_{chat_id}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "⚙️ Group Settings:",
        reply_markup=reply_markup
    )

def handle_settings_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data.split('_')
    action = data[0]
    chat_id = int(data[2])
    
    if action == 'toggle':
        group_settings[chat_id]['music_enabled'] = not group_settings[chat_id]['music_enabled']
        status = "ON" if group_settings[chat_id]['music_enabled'] else "OFF"
        query.edit_message_text(f"🎵 Music is now {status}")
    
    elif action == 'set':
        query.edit_message_text("Send your welcome message now:")
        return WAITING_WELCOME
    
    save_group_data()

def set_welcome_message(update: Update, context: CallbackContext):
    chat_id = update.message.chat.id
    welcome_messages[chat_id] = update.message.text
    group_settings[chat_id]['welcome_enabled'] = True
    save_group_data()
    update.message.reply_text("✅ Welcome message set!")
    return ConversationHandler.END

def welcome_new_member(update: Update, context: CallbackContext):
    chat_id = update.message.chat.id
    if chat_id in group_settings and group_settings[chat_id]['welcome_enabled']:
        for user in update.message.new_chat_members:
            if user.id == context.bot.id:
                continue  # Skip bot's own join
            update.message.reply_text(
                welcome_messages.get(chat_id, "Welcome to the group!").replace("{name}", user.first_name)
            )

# ====================== ADMIN FUNCTIONS ======================

def forward_to_admin(update: Update, context: CallbackContext):
    user = update.message.from_user
    
    if user.id in banned_users:
        update.message.reply_text("🚫 You are banned from using this bot.")
        return
    
    user_messages[user.id] = {
        'username': user.username or user.first_name,
        'chat_id': update.message.chat_id
    }
    
    context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📩 New message from {user.username or user.first_name} (ID: {user.id}):\n{update.message.text}"
    )
    update.message.reply_text("✅ Your message has been sent to admin!")

def admin_reply(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        update.message.reply_text("❌ Admin only command!")
        return
        
    if len(context.args) < 2:
        update.message.reply_text("Usage: /reply <user_id> <message>")
        return
    
    user_id = int(context.args[0])
    message = ' '.join(context.args[1:])
    
    if user_id in user_messages:
        context.bot.send_message(
            chat_id=user_messages[user_id]['chat_id'],
            text=f"💌 Admin reply: {message}"
        )
        update.message.reply_text(f"✅ Reply sent to {user_messages[user_id]['username']}!")
    else:
        update.message.reply_text("❌ User not found.")

# ====================== DATA MANAGEMENT ======================

def save_group_data():
    with open('group_data.json', 'w') as f:
        json.dump({
            'settings': group_settings,
            'welcome': welcome_messages
        }, f)

def load_group_data():
    try:
        with open('group_data.json') as f:
            data = json.load(f)
            group_settings.update(data.get('settings', {}))
            welcome_messages.update(data.get('welcome', {}))
    except (FileNotFoundError, json.JSONDecodeError):
        pass

# ====================== MAIN ======================

def main():
    load_group_data()
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # Conversation handler for welcome messages
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_settings_callback, pattern='^set_welcome_')],
        states={
            WAITING_WELCOME: [MessageHandler(Filters.text & ~Filters.command, set_welcome_message)]
        },
        fallbacks=[]
    )

    # Handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("play", play_music))
    dp.add_handler(CommandHandler("setup", setup_group))
    dp.add_handler(CommandHandler("settings", group_settings_menu))
    dp.add_handler(CommandHandler("reply", admin_reply))
    
    dp.add_handler(conv_handler)
    dp.add_handler(CallbackQueryHandler(handle_settings_callback))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, forward_to_admin))
    dp.add_handler(MessageHandler(Filters.status_update.new_chat_members, welcome_new_member))
    
    # Start the Bot
    updater.start_polling()
    logger.info("Bot is running with all features...")
    updater.idle()

if __name__ == '__main__':
    main()
