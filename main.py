import os
import logging
import json
import asyncio
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Updated imports for modern telegram bot
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

# Modern audio processing imports
import yt_dlp
import aiohttp
from pathlib import Path

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
user_limits = {}  # Rate limiting

# Conversation states
WAITING_WELCOME = 1

# ====================== UTILITY FUNCTIONS ======================

def check_rate_limit(user_id: int) -> bool:
    """Check if user has exceeded rate limit"""
    now = datetime.now()
    if user_id not in user_limits:
        user_limits[user_id] = []
    
    # Remove old entries
    user_limits[user_id] = [
        timestamp for timestamp in user_limits[user_id]
        if now - timestamp < timedelta(seconds=RATE_LIMIT_WINDOW)
    ]
    
    if len(user_limits[user_id]) >= RATE_LIMIT_MESSAGES:
        return False
    
    user_limits[user_id].append(now)
    return True

def is_admin(user_id: int, chat_id: int) -> bool:
    """Check if user is admin in group"""
    if user_id == ADMIN_ID:
        return True
    return chat_id in group_settings and user_id in group_settings[chat_id].get('admins', [])

# ====================== CORE FUNCTIONS ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    await update.message.reply_text(
        f"🎵 Hello {user.first_name}! I'm Muskan Music Bot!\n"
        "Use /help to see available commands."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🎶 *Available Commands:*

🔊 *Music:*
/play <song> - Play a song (192kbps HQ)
/search <song> - Search for songs
/queue - Show current playlist
/skip - Skip current song
/clear - Clear playlist

👥 *Group Management:*
/setup - Initialize bot in group
/settings - Configure group
/welcome <msg> - Set welcome message

💬 *Chat:*
/admin <message> - Contact admin
/reply <user_id> <msg> - Reply to user (Admin only)

⚙️ *Admin Only:*
/ban <user_id> - Ban user
/unban <user_id> - Unban user
/broadcast <msg> - Send to all users
/stats - Show bot statistics
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

# ====================== IMPROVED MUSIC FUNCTIONS ======================

async def play_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.message.chat.id
    
    # Check bans and rate limits
    if user_id in banned_users:
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return
    
    if not check_rate_limit(user_id):
        await update.message.reply_text("⏰ Please wait before sending another command.")
        return
    
    # Check if music is enabled in group
    if chat_id < 0:  # Group chat
        if chat_id not in group_settings or not group_settings[chat_id].get('music_enabled', True):
            await update.message.reply_text("❌ Music is disabled in this group")
            return
    
    if not context.args:
        await update.message.reply_text("Please specify a song after /play\nExample: `/play Never Gonna Give You Up`", parse_mode='Markdown')
        return
    
    query = ' '.join(context.args)
    
    try:
        # Send "searching" message
        searching_msg = await update.message.reply_text("🔍 Searching for your song...")
        
        # Modern yt-dlp configuration
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': '%(title)s.%(ext)s'
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(f"ytsearch:{query}", download=False)
                if not info['entries']:
                    await searching_msg.edit_text("❌ No songs found for your query")
                    return
                    
                video_info = info['entries'][0]
                title = video_info['title']
                duration = video_info.get('duration', 0)
                uploader = video_info.get('uploader', 'Unknown')
                
                if duration > 900:  # 15 minute limit
                    await searching_msg.edit_text("❌ Songs longer than 15 minutes aren't supported")
                    return
                
                # Add to queue
                music_queue.append({
                    'info': video_info,
                    'title': title,
                    'duration': duration,
                    'uploader': uploader,
                    'requested_by': user_id,
                    'chat_id': chat_id,
                    'username': update.message.from_user.username or update.message.from_user.first_name
                })
                
                duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Unknown"
                await searching_msg.edit_text(
                    f"🎧 *Added to queue:*\n"
                    f"🎵 {title}\n"
                    f"⏱️ Duration: {duration_str}\n"
                    f"👤 By: {uploader}\n"
                    f"📍 Position: {len(music_queue)}",
                    parse_mode='Markdown'
                )
                
                # Start playing if this is the first song
                if len(music_queue) == 1:
                    await send_music(update, context)
                    
            except Exception as e:
                await searching_msg.edit_text(f"❌ Error searching: {str(e)}")
                logger.error(f"Search error: {str(e)}")
                
    except Exception as e:
        await update.message.reply_text(f"❌ Unexpected error: {str(e)}")
        logger.error(f"Music error: {str(e)}")

async def send_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not music_queue:
        return
        
    current_song = music_queue[0]
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Send "downloading" message
        downloading_msg = await context.bot.send_message(
            chat_id=current_song['chat_id'],
            text="⬇️ Downloading song..."
        )
        
        # Download with yt-dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([current_song['info']['webpage_url']])
        
        # Find the downloaded file
        downloaded_files = list(Path(temp_dir).glob('*.mp3'))
        if not downloaded_files:
            await downloading_msg.edit_text("❌ Download failed")
            return
            
        audio_file = downloaded_files[0]
        
        # Check file size (50MB limit)
        if audio_file.stat().st_size > 50 * 1024 * 1024:
            await downloading_msg.edit_text("❌ File too large (>50MB)")
            return
        
        await downloading_msg.edit_text("📤 Uploading song...")
        
        # Send the audio file
        with open(audio_file, 'rb') as audio:
            await context.bot.send_audio(
                chat_id=current_song['chat_id'],
                audio=audio,
                title=current_song['title'],
                performer=current_song['uploader'],
                duration=current_song['duration'],
                caption=f"🎵 Requested by @{current_song['username']}"
            )
        
        await downloading_msg.delete()
        
        # Remove from queue and play next
        music_queue.pop(0)
        if music_queue:
            await send_music(update, context)
        else:
            await context.bot.send_message(
                chat_id=current_song['chat_id'],
                text="🎵 Queue is empty! Add more songs with /play"
            )
            
    except Exception as e:
        await context.bot.send_message(
            chat_id=current_song['chat_id'],
            text=f"❌ Playback error: {str(e)}"
        )
        logger.error(f"Playback error: {str(e)}")
    finally:
        # Cleanup temp files
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except Exception as e: # Catch any exception during cleanup
            logger.error(f"Error cleaning up temp directory {temp_dir}: {e}") # Log cleanup errors

async def search_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if user_id in banned_users:
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return
    
    if not context.args:
        await update.message.reply_text("Please specify a search query after /search")
        return
    
    query = ' '.join(context.args)
    
    try:
        searching_msg = await update.message.reply_text("🔍 Searching...")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            
            if not info['entries']:
                await searching_msg.edit_text("❌ No results found")
                return
            
            results = []
            for i, entry in enumerate(info['entries'][:5], 1):
                duration = entry.get('duration', 0)
                duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Unknown"
                results.append(f"{i}. **{entry['title']}**\n    ⏱️ {duration_str} | 👤 {entry.get('uploader', 'Unknown')}")
            
            await searching_msg.edit_text(
                f"🔍 **Search Results for:** {query}\n\n" + "\n\n".join(results),
                parse_mode='Markdown'
            )
            
    except Exception as e:
        await update.message.reply_text(f"❌ Search error: {str(e)}")

async def show_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not music_queue:
        await update.message.reply_text("📭 Queue is empty!")
        return
    
    queue_text = "🎵 **Current Queue:**\n\n"
    for i, song in enumerate(music_queue[:10], 1):  # Show first 10 songs
        duration = song['duration']
        duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Unknown"
        queue_text += f"{i}. **{song['title']}**\n    ⏱️ {duration_str} | 👤 @{song['username']}\n\n"
    
    if len(music_queue) > 10:
        queue_text += f"... and {len(music_queue) - 10} more songs"
    
    await update.message.reply_text(queue_text, parse_mode='Markdown')

async def skip_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    
    if not music_queue:
        await update.message.reply_text("📭 No songs in queue to skip!")
        return
    
    # Check if user is admin or the one who requested the song
    if not is_admin(user_id, chat_id) and music_queue[0]['requested_by'] != user_id:
        await update.message.reply_text("❌ Only admins or the song requester can skip songs")
        return
    
    skipped_song = music_queue.pop(0)
    await update.message.reply_text(f"⏭️ Skipped: {skipped_song['title']}")
    
    if music_queue:
        await send_music(update, context)
    else:
        await context.bot.send_message(
                chat_id=current_song['chat_id'],
                text="🎵 Queue is empty! Add more songs with /play"
            )
            
    except Exception as e:
        await context.bot.send_message(
            chat_id=current_song['chat_id'],
            text=f"❌ Playback error: {str(e)}"
        )
        logger.error(f"Playback error: {str(e)}")
    finally:
        # Cleanup temp files
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except Exception as e: # Catch any exception during cleanup
            logger.error(f"Error cleaning up temp directory {temp_dir}: {e}") # Log cleanup errors

async def search_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if user_id in banned_users:
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return
    
    if not context.args:
        await update.message.reply_text("Please specify a search query after /search")
        return
    
    query = ' '.join(context.args)
    
    try:
        searching_msg = await update.message.reply_text("🔍 Searching...")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            
            if not info['entries']:
                await searching_msg.edit_text("❌ No results found")
                return
            
            results = []
            for i, entry in enumerate(info['entries'][:5], 1):
                duration = entry.get('duration', 0)
                duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Unknown"
                results.append(f"{i}. **{entry['title']}**\n    ⏱️ {duration_str} | 👤 {entry.get('uploader', 'Unknown')}")
            
            await searching_msg.edit_text(
                f"🔍 **Search Results for:** {query}\n\n" + "\n\n".join(results),
                parse_mode='Markdown'
            )
            
    except Exception as e:
        await update.message.reply_text(f"❌ Search error: {str(e)}")

async def show_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not music_queue:
        await update.message.reply_text("📭 Queue is empty!")
        return
    
    queue_text = "🎵 **Current Queue:**\n\n"
    for i, song in enumerate(music_queue[:10], 1):  # Show first 10 songs
        duration = song['duration']
        duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Unknown"
        queue_text += f"{i}. **{song['title']}**\n    ⏱️ {duration_str} | 👤 @{song['username']}\n\n"
    
    if len(music_queue) > 10:
        queue_text += f"... and {len(music_queue) - 10} more songs"
    
    await update.message.reply_text(queue_text, parse_mode='Markdown')

async def skip_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    
    if not music_queue:
        await update.message.reply_text("📭 No songs in queue to skip!")
        return
    
    # Check if user is admin or the one who requested the song
    if not is_admin(user_id, chat_id) and music_queue[0]['requested_by'] != user_id:
        await update.message.reply_text("❌ Only admins or the song requester can skip songs")
        return
    
    skipped_song = music_queue.pop(0)
    await update.message.reply_text(f"⏭️ Skipped: {skipped_song['title']}")
    
    if music_queue:
        await send_music(update, context)
    else:
        await context.bot.send_message(
            chat_id=current_song['chat_id'], # ERROR HERE: current_song not defined
            text="🎵 Queue is empty! Add more songs with /play"
        )

async def clear_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    
    if not is_admin(user_id, chat_id):
        await update.message.reply_text("❌ Only admins can clear the queue")
        return
    
    music_queue.clear()
    await update.message.reply_text("🗑️ Queue cleared!")

# Placeholder for future functions (add these in main too if you implement them)
async def now_playing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("`now_playing` command not yet implemented.")

async def shuffle_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("`shuffle_queue` command not yet implemented.")

async def remove_song(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("`remove_song` command not yet implemented.")

async def lyrics_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("`lyrics_search` command not yet implemented.")

async def set_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("`set_volume` command not yet implemented.")

async def user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("`user_stats` command not yet implemented.")


# ====================== GROUP MANAGEMENT ======================

async def setup_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    
    if chat_id > 0:  # Private chat
        await update.message.reply_text("❌ This command is for groups only")
        return
    
    if chat_id not in group_settings:
        group_settings[chat_id] = {
            'admins': [user_id],
            'music_enabled': True,
            'welcome_enabled': False
        }
        await save_group_data()
        await update.message.reply_text("✅ Group setup complete! Use /settings to configure")
    else:
        await update.message.reply_text("ℹ️ Group already setup")

async def group_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    
    if chat_id > 0:
        await update.message.reply_text("❌ This command is for groups only")
        return
    
    if not is_admin(user_id, chat_id):
        await update.message.reply_text("❌ Only admins can access settings")
        return
    
    if chat_id not in group_settings:
        await update.message.reply_text("❌ Group not setup. Use /setup first")
        return
    
    settings = group_settings[chat_id]
    music_status = "🔊 ON" if settings['music_enabled'] else "🔇 OFF"
    welcome_status = "✅ ON" if settings['welcome_enabled'] else "❌ OFF"
    
    keyboard = [
        [InlineKeyboardButton(f"Music: {music_status}", callback_data=f'toggle_music_{chat_id}')],
        [InlineKeyboardButton(f"Welcome: {welcome_status}", callback_data=f'toggle_welcome_{chat_id}')],
        [InlineKeyboardButton("👥 Admin List", callback_data=f'admin_list_{chat_id}')],
        [InlineKeyboardButton("🔧 Set Welcome Message", callback_data=f'set_welcome_{chat_id}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⚙️ **Group Settings:**\n\n"
        f"🎵 Music: {music_status}\n"
        f"👋 Welcome: {welcome_status}\n"
        f"👥 Admins: {len(settings['admins'])}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    action = data[0]
    feature = data[1]
    chat_id = int(data[2])
    
    if action == 'toggle':
        if feature == 'music':
            group_settings[chat_id]['music_enabled'] = not group_settings[chat_id]['music_enabled']
            status = "ON" if group_settings[chat_id]['music_enabled'] else "OFF"
            await query.edit_message_text(f"🎵 Music is now {status}")
        elif feature == 'welcome':
            group_settings[chat_id]['welcome_enabled'] = not group_settings[chat_id]['welcome_enabled']
            status = "ON" if group_settings[chat_id]['welcome_enabled'] else "OFF"
            await query.edit_message_text(f"👋 Welcome messages are now {status}")
    
    elif action == 'admin' and feature == 'list':
        admins = group_settings[chat_id]['admins']
        admin_list = "\n".join([f"• {admin_id}" for admin_id in admins])
        await query.edit_message_text(f"👥 **Group Admins:**\n{admin_list}", parse_mode='Markdown')
    
    elif action == 'set' and feature == 'welcome':
        # Store context for the conversation handler
        context.user_data['setting_welcome_for_chat_id'] = chat_id
        await query.edit_message_text("Send your welcome message now:")
        return WAITING_WELCOME
    
    await save_group_data()

async def set_welcome_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.user_data.get('setting_welcome_for_chat_id', update.message.chat.id) # Use stored chat_id
    welcome_messages[chat_id] = update.message.text
    group_settings[chat_id]['welcome_enabled'] = True
    await save_group_data()
    await update.message.reply_text("✅ Welcome message set!")
    return ConversationHandler.END

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    if chat_id in group_settings and group_settings[chat_id]['welcome_enabled']:
        for user in update.message.new_chat_members:
            if user.id == context.bot.id:
                continue  # Skip bot's own join
            message = welcome_messages.get(chat_id, "👋 Welcome to the group, {name}!")
            await update.message.reply_text(
                message.replace("{name}", user.first_name),
                parse_mode='Markdown'
            )

# ====================== ADMIN FUNCTIONS ======================

async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    
    if user.id in banned_users:
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏰ Please wait before sending another message.")
        return
    
    user_messages[user.id] = {
        'username': user.username or user.first_name,
        'chat_id': update.message.chat_id,
        'first_name': user.first_name
    }
    
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📩 **New message from** {user.first_name} (@{user.username or 'no_username'})\n"
             f"**ID:** {user.id}\n"
             f"**Message:** {update.message.text}",
        parse_mode='Markdown'
    )
    await update.message.reply_text("✅ Your message has been sent to admin!")

async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only command!")
        return
        
    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/reply <user_id> <message>`", parse_mode='Markdown')
        return
    
    try:
        user_id = int(context.args[0])
        message = ' '.join(context.args[1:])
        
        if user_id in user_messages:
            # Ensure the reply is sent to the correct chat_id where the user last messaged the bot
            # Note: user_messages[user_id]['chat_id'] stores the chat_id from the last message the user sent to the bot,
            # which might be a group chat if they contacted via /admin from there.
            # For direct replies, it might be better to store a 'private_chat_id' if you want direct user DM.
            # For now, it sends back to the chat where the last /admin message was received.
            await context.bot.send_message(
                chat_id=user_messages[user_id]['chat_id'],
                text=f"💌 **Admin reply:** {message}",
                parse_mode='Markdown'
            )
            await update.message.reply_text(f"✅ Reply sent to {user_messages[user_id]['first_name']}!")
        else:
            await update.message.reply_text("❌ User not found or hasn't messaged the bot.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only command!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/ban <user_id>`", parse_mode='Markdown')
        return
    
    try:
        user_id = int(context.args[0])
        banned_users.add(user_id)
        await update.message.reply_text(f"🚫 User {user_id} has been banned.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only command!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/unban <user_id>`", parse_mode='Markdown')
        return
    
    try:
        user_id = int(context.args[0])
        banned_users.discard(user_id)
        await update.message
