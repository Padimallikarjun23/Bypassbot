# bot.py (formerly plugins/bypass_handler.py - updated for MongoDB support)

import re
import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatAction, ParseMode
from pyrogram.errors import PeerIdInvalid, ChatAdminRequired, UserNotParticipant, FloodWait, MessageDeleteForbidden, MessageNotModified
from .user_manager import user_manager
from database import db  # Import the MongoDB instance from database.py
from config import *

# Initialize user client (for bypass communication only)
user_client = Client(
    name="bypass_session",
    api_id=BYPASS_API_ID,
    api_hash=BYPASS_API_HASH,
    session_string=BYPASS_SESSION_STRING,
    in_memory=True
)

# Animation frames for processing
LOADING_EMOJIS = ["⏳", "🔄", "⚡", "🚀", "💫", "✨", "🌟", "⭐"]

async def safe_delete_message(bot, chat_id, message_id, delay_seconds=60):
    """Delete message after delay, ignoring errors"""
    await asyncio.sleep(delay_seconds)
    try:
        await bot.delete_messages(chat_id, message_id)
        print(f"[DEBUG] Auto-deleted message {message_id} in chat {chat_id}")
    except (MessageDeleteForbidden, Exception) as e:
        print(f"[DEBUG] Could not delete message {message_id}: {e}")

async def safe_edit_message(bot, chat_id, message_id, text, reply_markup=None, parse_mode=ParseMode.MARKDOWN):
    """Safely edit message with error handling"""
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        return True
    except (MessageNotModified, Exception) as e:
        print(f"[DEBUG] Error editing message: {e}")
        return False

async def animate_processing_message(message, duration=15):
    """Animate processing message with different frames"""
    try:
        for i in range(duration):
            emoji = LOADING_EMOJIS[i % len(LOADING_EMOJIS)]
            dots = "." * (i % 4)
            text = f"{emoji} Bypassing your links{dots}\n\n🎯 **Status:** Processing...\n⏱️ **Time:** {i+1}s\n🔥 **Please wait patiently!**"
            
            try:
                await message.edit_text(text, parse_mode=ParseMode.MARKDOWN)
                await asyncio.sleep(1)
            except (MessageNotModified, Exception):
                break
    except Exception as e:
        print(f"[DEBUG] Animation error: {e}")

async def safe_send_message(bot, chat_id, text, reply_to_message_id=None, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True, reply_markup=None):
    """Safely send message with error handling"""
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_to_message_id=reply_to_message_id,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"[DEBUG] Error sending message to {chat_id}: {e}")
        # Fallback without markdown
        try:
            return await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_to_message_id=reply_to_message_id,
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )
        except Exception as e2:
            print(f"[DEBUG] Complete send failure: {e2}")
            return None

async def safe_copy_message(message, chat_id, reply_to_message_id=None):
    """Safely copy message with error handling"""
    try:
        await message.copy(
            chat_id=chat_id,
            reply_to_message_id=reply_to_message_id
        )
        return True
    except Exception as e:
        print(f"[DEBUG] Error copying message to {chat_id}: {e}")
        return False

def make_clickable_link(text, url):
    """Create a clickable markdown link - FIXED VERSION"""
    # Clean the text and URL
    safe_text = str(text).replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)')
    clean_url = str(url).strip()
    
    # Return markdown link format
    return f"[{safe_text}]({clean_url})"

def extract_multiple_links(text):
    """Extract multiple links from text - supports comma, space, and newline separation"""
    # Remove command prefix
    text = re.sub(r'^/by\s*|^!by\s*', '', text, flags=re.IGNORECASE).strip()
    
    # Find all URLs in the text
    urls = re.findall(r'https?://[^\s,\n]+', text)
    
    # Clean URLs (remove trailing punctuation)
    cleaned_urls = []
    for url in urls:
        url = re.sub(r'[,\.\)]+$', '', url)
        if url:
            cleaned_urls.append(url)
    
    return cleaned_urls

async def init_user_client():
    global user_client
    try:
        if user_client and getattr(user_client, "is_connected", False):
            await user_client.stop()
        await user_client.start()
        print("[DEBUG] User client initialized and started successfully")
        return True
    except Exception as e:
        print(f"[DEBUG] Failed to initialize user client: {e}")
        return False

# --- Season Storage in MongoDB ---
async def load_season_store(key):
    """Load season from MongoDB"""
    doc = db.season_store.find_one({'_id': key})
    return doc.get('season') if doc else None

async def save_season_store(key, season):
    """Save season to MongoDB"""
    try:
        db.season_store.update_one({'_id': key}, {'$set': {'season': season}}, upsert=True)
    except Exception as e:
        print(f"Error saving season store: {e}")

pending_bypass_requests = {}
bot_instance = None

def set_bot_instance(bot):
    global bot_instance
    bot_instance = bot

def extract_links_from_text_and_buttons(text, reply_markup):
    """Enhanced function to extract links from both text and inline buttons"""
    bypassed_links = []
    title = ""
    size = ""
    
    print(f"[DEBUG] Processing text: {text[:200] if text else 'No text'}...")
    
    if text:
        for line in text.splitlines():
            line = line.strip()
            if "📚 Title" in line and ":-" in line:
                title = line.split(":-", 1)[1].strip()
                print(f"[DEBUG] Found title: {title}")
            elif "💾 Size" in line and ":-" in line:
                size = line.split(":-", 1)[1].strip()
                print(f"[DEBUG] Found size: {size}")
    
    link_types_order = []
    if text:
        for line in text.splitlines():
            line = line.strip()
            if ":-" in line and any(keyword in line for keyword in ["GoFile", "Download", "Telegram", "Mega", "Stream"]):
                if "📂 GoFile" in line:
                    link_types_order.append("GoFile")
                elif "🔗 Download" in line:
                    link_types_order.append("Download Link")
                elif "☁️ Telegram" in line:
                    link_types_order.append("Telegram")
                elif "📦 Mega" in line:
                    link_types_order.append("Mega")
                elif "🎥 Stream" in line:
                    link_types_order.append("Stream")
                print(f"[DEBUG] Found link type in text: {link_types_order[-1]}")
    
    if text:
        for line in text.splitlines():
            line = line.strip()
            if "🔓 Bypassed Link" in line:
                url_match = re.search(r'https?://\S+', line)
                if url_match:
                    url = url_match.group(0)
                    bypassed_links.append(("Direct Link", url))
                    print(f"[DEBUG] Found direct bypassed link in text: {url}")
    
    if reply_markup and isinstance(reply_markup, InlineKeyboardMarkup):
        print("[DEBUG] Processing inline buttons")
        button_links = []
        for row in reply_markup.inline_keyboard:
            for btn in row:
                if hasattr(btn, 'url') and btn.url:
                    skip_patterns = ['dd_bypass_updates', '/DD_Bypass', 'support', 'how to download']
                    should_skip = any(pattern in btn.url.lower() for pattern in skip_patterns) or any(word in btn.text.lower() for word in ['update', 'channel', 'support', 'how to'])
                    if should_skip:
                        print(f"[DEBUG] Skipping promotional button: {btn.text} -> {btn.url}")
                        continue
                    button_links.append(btn.url)

        for i, url in enumerate(button_links):
            link_type = link_types_order[i] if i < len(link_types_order) else (
                "GoFile" if 'gofile' in url.lower() else
                "Mega" if 'mega' in url.lower() else
                "Telegram" if 't.me/' in url.lower() and 'bot' in url.lower() else
                "Download Link" if any(x in url.lower() for x in ['drive', 'mediafire', 'download']) else
                "Link"
            )
            bypassed_links.append((link_type, url))

    if text:
        markdown_matches = re.finditer(r'\[([^\]]+)\]\s*\(\s*(https?://[^)\s]+)\s*\)', text)
        for match in markdown_matches:
            link_text = match.group(1).strip()
            url = match.group(2).strip()
            url = re.sub(r'[,\.\)]+$', '', url)
            link_type = (
                "GoFile" if 'gofile' in url.lower() or 'gofile' in link_text.lower() else
                "Mega" if 'mega' in url.lower() or 'mega' in link_text.lower() else
                "Telegram" if ('t.me/' in url.lower() and 'bot' in url.lower()) or 'telegram' in link_text.lower() else
                "Download Link" if any(x in url.lower() or x in link_text.lower() for x in ['drive', 'mediafire', 'download']) else
                "Stream" if 'stream' in link_text.lower() or 'watch' in link_text.lower() else
                "Link"
            )
            bypassed_links.append((link_type, url))

    if not bypassed_links and text:
        all_urls = re.findall(r'https?://[^\s\)]+', text)
        for url in all_urls:
            url = re.sub(r'[,\.\)]+$', '', url)
            bypassed_links.append(("Direct Link", url))

    return bypassed_links, title, size

def parse_multi_link_response(text):
    """Parse multi-link response from DD bypass bot"""
    results = []
    
    # Split response by the separator
    sections = text.split("━━━━━━━✦✗✦━━━━━━━")
    
    for section in sections:
        section = section.strip()
        if not section:
            continue
            
        original_link = ""
        bypassed_link = ""
        
        # Extract original and bypassed links from each section
        for line in section.splitlines():
            line = line.strip()
            if "🔗 Original Link" in line and ":-" in line:
                original_link = line.split(":-", 1)[1].strip()
            elif "🔓 Bypassed Link" in line and ":" in line:
                bypassed_link = line.split(":", 1)[1].strip()
        
        if original_link and bypassed_link:
            results.append((original_link, bypassed_link))
            print(f"[DEBUG] Parsed link pair: {original_link} -> {bypassed_link}")
    
    return results

@user_client.on_message()
async def handle_bypass_response(client, message):
    if not message.chat or message.chat.username != BYPASS_BOT_USERNAME.lstrip("@"):
        return
        
    text = message.text or ""
    
    # Progress update with animation
    if "Bypassing" in text:
        for req in pending_bypass_requests.values():
            if any(link in text for link in req["original_link"].split()) and req.get("status_msg"):
                try:
                    emoji = LOADING_EMOJIS[0]
                    await req["status_msg"].edit_text(f"{emoji} **Bot is processing your links...**\n\n🔄 **Status:** In Progress\n⏰ **Please wait...**", parse_mode=ParseMode.MARKDOWN)
                except:
                    pass
        return
    
    is_final_result = False
    should_forward = False
    is_multi_link = False
    
    if text:
        if "┎ 📚 Title" in text and "┠ 💾 Size" in text:
            is_final_result = True
            should_forward = True
            print("[DEBUG] Found title and size format - will forward directly")
        elif "┎ 🔗 Original Link" in text and "🔓 Bypassed Link" in text:
            is_final_result = True
            should_forward = False
            # Check if it's multi-link response
            if text.count("━━━━━━━✦✗✦━━━━━━━") > 0:
                is_multi_link = True
                print("[DEBUG] Found multi-link bypass format")
            else:
                print("[DEBUG] Found single bypass link format")
    
    if not is_final_result:
        return
    
    # Match request
    matching_id = None
    for rid, req in pending_bypass_requests.items():
        original_links = req["original_link"].split()
        if any(link in text for link in original_links):
            matching_id = rid
            break
    
    if not matching_id and pending_bypass_requests:
        matching_id = max(pending_bypass_requests, key=lambda k: pending_bypass_requests[k]["time_sent"])
    
    if not matching_id:
        print("[DEBUG] No matching request found")
        return
    
    req = pending_bypass_requests.pop(matching_id)
    group_id = req["group_id"]
    original_msg_id = req["original_msg_id"]
    
    # Update status to completing
    if req.get("status_msg"):
        try:
            await req["status_msg"].edit_text("✅ **Bypass Complete!** Sending results...", parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(1)
        except:
            pass
    
    # Delete status message
    if req.get("status_msg"):
        try:
            await req["status_msg"].delete()
        except:
            pass
    
    if should_forward:
        success = await safe_copy_message(message, group_id, original_msg_id)
        if success:
            print("[DEBUG] Successfully forwarded the bypass result")
            return
        print("[DEBUG] Forward failed, will format manually")
    
    # Handle multi-link response
    if is_multi_link:
        link_pairs = parse_multi_link_response(text)
        if link_pairs:
            formatted_sections = []
            
            for i, (original, bypassed) in enumerate(link_pairs, 1):
                section = (
                    f"**🔗 Link {i}:**\n"
                    f"**Original:** {make_clickable_link('Click Here', original)}\n"
                    f"**Bypassed:** {make_clickable_link('Bypassed Link', bypassed)}\n"
                )
                formatted_sections.append(section)
            
            formatted_text = (
                f"🎉 **Multi-Link Bypass Successful!** 🎉\n\n"
                f"**📊 Total Links:** {len(link_pairs)}\n\n"
                + "\n━━━━━━━━━━━━━━━━━━━━\n\n".join(formatted_sections) +
                f"\n\n⚡ **Powered by @Malli4U_Official2**\n"
                f"👤 **Requested by:** {req['user_id']}\n"
                f"⏰ **Time:** {datetime.now().strftime('%H:%M:%S')}"
            )
            
            await safe_send_message(bot_instance, group_id, formatted_text, original_msg_id)
            print(f"[DEBUG] Successfully sent multi-link bypass result with {len(link_pairs)} links")
            return
    
    # Handle single link response (existing code)
    if "┎ 🔗 Original Link" in text and "🔓 Bypassed Link" in text:
        original_link = ""
        bypassed_link = ""
        
        for line in text.splitlines():
            line = line.strip()
            if "Original Link" in line and ":-" in line:
                original_link = line.split(":-", 1)[1].strip()
            elif "Bypassed Link" in line and ":" in line:
                bypassed_link = line.split(":", 1)[1].strip()
        
        if original_link and bypassed_link:
            formatted_text = (
                "✨ **Bypass Successful!** ✨\n\n"
                f"**🔗 Original Link:** {make_clickable_link('Click Here', original_link)}\n\n"
                f"**🚀 Bypassed Link:** {make_clickable_link('Bypassed Link', bypassed_link)}\n\n"
                f"⚡ **Powered by @Malli4U_Official2**\n"
                f"🙍 **Requested by:** {req['user_id']}\n"
                f"⏰ **Time:** {datetime.now().strftime('%H:%M:%S')}"
            )
            
            await safe_send_message(bot_instance, group_id, formatted_text, original_msg_id)
            print("[DEBUG] Successfully sent formatted bypass message with clickable links")
            return
    
    # Fallback: Try to extract links and format with CLICKABLE LINKS
    bypassed_links, title, size = extract_links_from_text_and_buttons(text, message.reply_markup)
    
    if not bypassed_links:
        await safe_send_message(
            bot_instance, 
            group_id, 
            "❌ **Bypass Failed**\n\nCould not process the bypass response. Please try again or contact support.\n\n🆘 **Support:** @M4U_Admin_Bot", 
            original_msg_id
        )
        return
    
    # Format message with CLICKABLE LINKS - FIXED VERSION
    formatted = ["🎉 **Bypass Successful!** 🎉\n"]
    formatted.append(f"**📋 Original Link:** {make_clickable_link('🔗 Click Here', req['original_link'])}\n")
    
    if title:
        formatted.append(f"**📚 Title:** {title}\n")
    if size:
        formatted.append(f"**💾 Size:** {size}\n")
    
    formatted.append("**🎯 Download Links:**\n")
    
    for i, (link_type, link_url) in enumerate(bypassed_links, 1):
        emoji_map = {
            "GoFile": "📂",
            "Mega": "📦", 
            "Telegram": "☁️",
            "Stream": "🎥",
            "Download Link": "🔗"
        }
        
        emoji = emoji_map.get(link_type, "🔗")
        link_name = f"{emoji} Download {link_type}"
        
        # Create clickable link
        clickable = make_clickable_link(link_name, link_url)
        formatted.append(f"**{i}.** {clickable}\n")
    
    formatted.append(f"\n⚡ **Powered by @Malli4U_Admin_Bot**\n👤 **Requested by:** {req['user_id']}\n⏰ **Time:** {datetime.now().strftime('%H:%M:%S')}")
    final_text = "\n".join(formatted)
    
    await safe_send_message(bot_instance, group_id, final_text, original_msg_id)
    print("[DEBUG] Successfully sent formatted message with ALL CLICKABLE LINKS")

# SIMPLIFIED Start command - NO SESSION MANAGEMENT
@Client.on_message(filters.command("start"))
async def start_command(bot: Client, message: Message):
    global bot_instance
    bot_instance = bot
    
    if message.from_user:
        user_manager.add_user(message.from_user.id)
    
    if message.from_user and user_manager.is_banned(message.from_user.id):
        return await message.reply("❌ You are banned from using this bot. Contact admin for support.")
    
    user_id = message.from_user.id
    chat_type = message.chat.type
    
    # Get user info
    is_premium = user_manager.is_premium(user_id)
    is_admin = user_manager.is_admin(user_id)
    daily_usage = user_manager.get_daily_usage(user_id)
    
    status_emoji = "👑" if is_admin else "💎" if is_premium else "🆓"
    status_text = "Admin" if is_admin else "Premium User" if is_premium else "Free User"
    usage_text = "∞" if (is_premium or is_admin) else f"{daily_usage}/3"
    
    # SIMPLE keyboard with URL buttons and basic callback buttons
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📚 How to Use", callback_data="howto"),
            InlineKeyboardButton("💎 Premium Details", callback_data="premium")
        ],
        [
            InlineKeyboardButton("📊 My Stats", callback_data="stats"),
            InlineKeyboardButton("🌟 Features", callback_data="features")
        ],
        [
            InlineKeyboardButton("👨‍💻 Developer", url="http://t.me/Malli4U_Admin_Bot"),
            InlineKeyboardButton("📢 Updates", url="https://t.me/Malli4U_Official2")
        ],
        [
            InlineKeyboardButton("🆘 Support", url="https://t.me/M4U_Admin_Bot")
        ]
    ])
    
    welcome_text = (
        f"🪬 **Welcome to Malli4U Bypass Bot!** 🪬\n\n"
        f"🚀 **Powered by Malli4U** | Built with ❤️\n\n"
        f"{status_emoji} **Your Status:** {status_text}\n"
        f"📈 **Today's Usage:** {usage_text} requests\n\n"
        f"✨ **What I Can Do:**\n"
        f"┣ 🔓 Bypass single or multiple shortened links\n"
        f"┣ 🎬 Animated processing with status updates\n"
        f"┣ 🔗 Generate clickable download links\n"
        f"┣ 💎 Premium subscription system\n"
        f"┣ 📊 Advanced usage tracking\n"
        f"┣ 🛡️ Anti-spam & rate limiting\n"
        f"┣ 🎨 Beautiful formatted results\n"
        f"┗ ⚡ Lightning fast processing\n\n"
        f"🎮 **Available Commands:**\n"
        f"┣ `/by <link>` - Bypass single link\n"
        f"┣ `/by <link1>, <link2>` - Bypass multiple links\n"
        f"┣ `/help` - Show detailed help guide\n"
        f"┣ `/stats` - View your statistics\n"
        f"┣ `/commands` - Show all commands\n"
        f"┗ Click buttons below for quick access!\n\n"
        f"💎 **Premium Benefits:**\n"
        f"┣ ♾️ Unlimited daily requests\n"
        f"┣ ⚡ Priority processing queue\n"
        f"┣ 💬 Private chat access\n"
        f"┣ 🎁 Exclusive features\n"
        f"┗ 👑 VIP support\n\n"
        f"🔥 **Join our community & get premium access!**\n"
        f"💰 **Price:** Just ₹25 for 30 days unlimited access!\n\n"
        f"⚡ **Developer:** {make_clickable_link('Contact Here', 'http://t.me/M4U_Admin_Bot')}\n"
        f"📢 **Updates:** {make_clickable_link('Malli4U Official', 'https://t.me/Malli4U_Official2')}"
    )
    
    sent_message = await safe_send_message(
        bot, message.chat.id, welcome_text, 
        reply_to_message_id=message.id, 
        reply_markup=keyboard
    )
    
    # Auto-delete welcome message in groups after 60 seconds
    if sent_message and chat_type in ["group", "supergroup"]:
        asyncio.create_task(safe_delete_message(bot, sent_message.chat.id, sent_message.id, 60))

# Help Command Handler
@Client.on_message(filters.command("help"))
async def help_command(bot: Client, message: Message):
    if message.from_user and user_manager.is_banned(message.from_user.id):
        return await message.reply("❌ You are banned from using this bot.")
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔙 Back to Start", callback_data="back_start"),
            InlineKeyboardButton("💎 Get Premium", url="https://t.me/M4U_Admin_Bot")
        ]
    ])
    
    help_text = (
        "📚 **Detailed Help Guide** 📚\n\n"
        "🎯 **How to Use Bypass Bot:**\n\n"
        "**Step 1:** Copy any shortened link(s)\n"
        "**Step 2:** Send `/by <your_link>` command\n"
        "**Step 3:** Watch the animated processing\n"
        "**Step 4:** Get clickable download links!\n\n"
        "📝 **Single Link Examples:**\n"
        "┣ `/by https://bit.ly/example123`\n"
        "┣ `/by https://tinyurl.com/sample`\n"
        "┣ `/by https://short.link/abc`\n"
        "┗ `/by https://ouo.io/xyz`\n\n"
        "🔗 **Multi-Link Examples:**\n"
        "┣ `/by https://bit.ly/link1, https://tinyurl.com/link2`\n"
        "┣ `/by https://short.link/abc https://ouo.io/xyz`\n"
        "┗ **Separate links with commas or spaces**\n\n"
        "🔗 **Supported Link Types:**\n"
        "┣ bit.ly, tinyurl.com, short.link\n"
        "┣ t.ly, linkvertise.com, etc.\n\n"
        "🆘 **Need Help?** Contact @M4U_Admin_Bot"
    )
    
    await safe_send_message(bot, message.chat.id, help_text, reply_markup=keyboard)

# Callback Query Handler (unchanged, but added sudo in stats if needed)
@Client.on_callback_query()
async def handle_callback_query(bot: Client, callback_query):
    data = callback_query.data
    message = callback_query.message
    user_id = callback_query.from_user.id
    
    back_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Start", callback_data="back_start")]
    ])
    
    if data == "howto":
        how_to_text = (
            "🎯 **How to Use Guide** 🎯\n\n"
            "**Step-by-Step Instructions:**\n\n"
            "**1.** Copy any shortened link(s) you want to bypass\n"
            "**2.** Send the command: `/by <your_link(s)>`\n"
            "**3.** Enjoy the animated processing status!\n"
            "**4.** Get clickable download links!\n\n"
            "📝 **Single Link Examples:**\n"
            "┣ `/by https://bit.ly/3ABC123`\n"
            "┣ `/by https://tinyurl.com/example`\n"
            "┣ `/by https://short.link/demo123`\n"
            "┗ `/by https://ouo.io/abcdef`\n\n"
            "🔗 **Multi-Link Examples:**\n"
            "┣ `/by https://bit.ly/link1, https://tinyurl.com/link2`\n"
            "┣ `/by https://short.link/abc https://ouo.io/xyz`\n"
            "┣ **Separate with commas or spaces**\n"
            "┗ **Process multiple links in one request!**\n\n"
            "✅ **What You'll Get:**\n"
            "┣ 📂 Clickable GoFile links\n"
            "┣ 📦 Clickable Mega links\n" 
            "┣ ☁️ Clickable Telegram links\n"
            "┣ 🎥 Clickable stream links\n"
            "┣ 🔗 Multi-link organized results\n"
            "┗ 🔗 All links are clickable!\n\n"
            "⚡ **Amazing Features:**\n"
            "┣ 🎬 Animated processing status\n"
            "┣ 💫 Real-time progress updates\n"
            "┣ 🎨 Beautiful result formatting\n"
            "┣ 🔗 Multi-link batch processing\n"
            "┣ 🔗 All links are clickable\n"
            "┣ ⏱️ Time stamps for results\n"
            "┗ 🚀 Lightning fast processing\n\n"
            "🆘 **Need Help?** Contact @Malli4U_Admin_Bot"
        )
        
        await safe_edit_message(bot, message.chat.id, message.id, how_to_text, back_keyboard)
    
    elif data == "premium":
        premium_text = (
            "💎 **Premium Subscription Details** 💎\n\n"
            "🎁 **Premium Benefits:**\n"
            "┣ ♾️ **Unlimited** daily bypass requests\n"
            "┣ ⚡ **Priority** processing queue\n"
            "┣ 💬 **Private chat** access allowed\n"
            "┣ 🎬 **Premium** animations & effects\n"
            "┣ 🔗 **Multi-link** batch processing\n"
            "┣ 🔗 **Enhanced** clickable links\n"
            "┣ 🎁 **Exclusive** features access\n"
            "┣ 👑 **VIP** customer support\n"
            "┗ 🚀 **5x faster** processing speed\n\n"
            "💰 **Pricing:**\n"
            "┣ **1 Month :** ₹25 → ₹0.83/day\n"
            "┣ **3 Months :** ₹70 → ₹0.78/day | 💸 Save ₹5\n"
            "┣ **6 Months :** ₹125 → ₹0.69/day | 💸 Save ₹25\n"
            "┗ **1 Year :** ₹250 → ₹0.68/day | 🏆 Save ₹50\n\n"
            "📞 **How to Get Premium:**\n"
            "1. Contact our admin: @Malli4U_Admin_Bot\n"
            "2. Choose your subscription plan\n"
            "3. Make payment (UPI/PayTM/GPay)\n"
            "4. Get instant premium activation!\n\n"
            "🎉 **Special Offer:** First-time users get 3 extra days FREE!\n\n"
            "🆘 **Questions?** Contact @Malli4U_Admin_Bot"
        )
        
        premium_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("💎 Buy Premium", url="http://t.me/Malli4U_Admin_Bot"),
                InlineKeyboardButton("🔙 Back", callback_data="back_start")
            ]
        ])
        
        await safe_edit_message(bot, message.chat.id, message.id, premium_text, premium_keyboard)
    
    elif data == "stats":
        if user_manager.is_admin(user_id):
            stats = user_manager.get_stats()
            sudo_list = user_manager.get_sudoers()
            sudo_text = "**Sudo Admins:**\n" + "\n".join([f"• {uid}" for uid in sudo_list]) if sudo_list else "No sudo admins"
            stats_text = (
                "👑 **Admin Dashboard** 👑\n\n"
                f"📊 **Bot Statistics:**\n"
                f"┣ 👥 **Total Users:** {stats['total_users']}\n"
                f"┣ 💎 **Premium Users:** {stats['premium_users']}\n"
                f"┣ 🚫 **Banned Users:** {stats['banned_users']}\n"
                f"┗ 🤖 **Bot Status:** Online ✅\n\n"
                f"{sudo_text}\n\n"
                f"⚡ **System Info:**\n"
                f"┣ 🌟 **Your Role:** Administrator\n"
                f"┣ 🔑 **Access Level:** Full Control\n"
                f"┣ 📈 **Performance:** Optimal\n"
                f"┣ 🎬 **Animations:** Active\n"
                f"┣ 🔗 **Multi-Link Support:** Enabled\n"
                f"┣ 🔗 **Clickable Links:** Enabled\n"
                f"┗ 🎯 **Bypass System:** Operational\n\n"
                f"🛠️ **Available Commands:**\n"
                f"┣ Use `/commands` for full list\n"
                f"┗ All admin functions active"
            )
        else:
            daily_usage = user_manager.get_daily_usage(user_id)
            is_premium = user_manager.is_premium(user_id)
            
            stats_text = (
                f"📊 **Your Personal Statistics** 📊\n\n"
                f"👤 **Account Info:**\n"
                f"┣ **User ID:** `{user_id}`\n"
                f"┣ **Status:** {'💎 Premium User' if is_premium else '🆓 Free User'}\n"
                f"┣ **Today's Usage:** {daily_usage}/{'∞' if is_premium else '3'}\n"
                f"┗ **Account Type:** {'VIP Access' if is_premium else 'Standard'}\n\n"
            )
            
            if is_premium:
                expiry = user_manager.get_premium_expiry(user_id)
                if expiry:
                    days_left = (expiry - datetime.now()).days
                    stats_text += (
                        f"⏰ **Premium Details:**\n"
                        f"┣ **Expires:** {expiry.strftime('%d %b %Y, %H:%M')}\n"
                        f"┣ **Days Left:** {days_left} days\n"
                        f"┣ **Status:** {'🟢 Active' if days_left > 0 else '🔴 Expired'}\n"
                        f"┗ **Renewal:** Contact admin\n\n"
                        f"🎁 **Your Benefits:**\n"
                        f"┣ ♾️ Unlimited requests\n"
                        f"┣ ⚡ Priority processing\n"
                        f"┣ 💬 Private chat access\n"
                        f"┣ 🎬 Premium animations\n"
                        f"┣ 🔗 Multi-link support\n"
                        f"┣ 🔗 Enhanced clickable links\n"
                        f"┗ 👑 VIP support"
                    )
            else:
                stats_text += (
                    f"🚀 **Upgrade to Premium:**\n"
                    f"┣ ♾️ Unlimited daily requests\n"
                    f"┣ ⚡ 5x faster processing\n"
                    f"┣ 💬 Private chat access\n"
                    f"┣ 🎬 Premium animations\n"
                    f"┣ 🔗 Multi-link support\n"
                    f"┣ 🔗 Enhanced clickable links\n"
                    f"┣ 🎁 Exclusive features\n"
                    f"┗ 👑 Priority support\n\n"
                    f"💰 **Special Price:** Only ₹25/month!\n"
                    f"📞 **Contact:** @Malli4U_Admin_Bot"
                )
        
        await safe_edit_message(bot, message.chat.id, message.id, stats_text, back_keyboard)
    
    elif data == "features":
        features_text = (
            "🌟 **Amazing Features** 🌟\n\n"
            "🎬 **Visual Experience:**\n"
            "┣ ⚡ Animated processing status\n"
            "┣ 🎨 Beautiful formatted results\n"
            "┣ 🔗 Clickable download links\n"
            "┣ 💫 Dynamic loading animations\n"
            "┣ 🔄 Real-time progress updates\n"
            "┗ ✨ Professional UI/UX\n\n"
            "🚀 **Performance Features:**\n"
            "┣ ⏱️ Lightning fast bypassing\n"
            "┣ 🔗 100+ supported shorteners\n"
            "┣ 📊 Advanced link detection\n"
            "┣ 🔗 Multi-link batch processing\n"
            "┣ 🛡️ Robust error handling\n"
            "┣ 🔄 Auto-retry on failures\n"
            "┗ 🎯 99% success rate\n\n"
            "👥 **User Experience:**\n"
            "┣ 📱 Works in groups & private\n"
            "┣ 🆓 Free tier with 3 daily requests\n"
            "┣ 💎 Premium unlimited access\n"
            "┣ 📈 Usage tracking & stats\n"
            "┣ 🔗 Multi-link support\n"
            "┣ 🔗 All links are clickable\n"
            "┗ 🆘 24/7 support available\n\n"
            "🔧 **Technical Features:**\n"
            "┣ 🛡️ Peer ID error handling\n"
            "┣ 📝 Session management\n"
            "┣ 🛡️ Anti-spam protection\n"
            "┣ ⚙️ Smart rate limiting\n"
            "┣ 🔄 Automatic error recovery\n"
            "┗ 📊 Advanced analytics\n\n"
            "💎 **Premium Features:**\n"
            "┣ ♾️ Unlimited daily requests\n"
            "┣ ⚡ Priority processing queue\n"
            "┣ 💬 Private chat access\n"
            "┣ 🎁 Exclusive animations\n"
            "┣ 🔗 Multi-link batch processing\n"
            "┣ 🔗 Enhanced link formatting\n"
            "┗ 👑 VIP support channel"
        )
        
        await safe_edit_message(bot, message.chat.id, message.id, features_text, back_keyboard)
    
    elif data == "back_start":
        # Go back to start message
        user_id = callback_query.from_user.id
        
        # Get user info
        is_premium = user_manager.is_premium(user_id)
        is_admin = user_manager.is_admin(user_id)
        daily_usage = user_manager.get_daily_usage(user_id)
        
        status_emoji = "👑" if is_admin else "💎" if is_premium else "🆓"
        status_text = "Admin" if is_admin else "Premium User" if is_premium else "Free User"
        usage_text = "∞" if (is_premium or is_admin) else f"{daily_usage}/3"
        
        # SIMPLE keyboard with URL buttons and basic callback buttons
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📚 How to Use", callback_data="howto"),
                InlineKeyboardButton("💎 Premium Details", callback_data="premium")
            ],
            [
                InlineKeyboardButton("📊 My Stats", callback_data="stats"),
                InlineKeyboardButton("🌟 Features", callback_data="features")
            ],
            [
                InlineKeyboardButton("👨‍💻 Developer", url="http://t.me/Malli4U_Admin_Bot"),
                InlineKeyboardButton("📢 Updates", url="https://t.me/Malli4U_Official2")
            ],
            [
                InlineKeyboardButton("🆘 Support", url="http://t.me/M4U_Admin_Bot")
            ]
        ])
        
        welcome_text = (
            f"🪬 **Welcome to Malli4U Bypass Bot!** 🪬\n\n"
            f"🚀 **Powered by Malli4U** | Built with ❤️\n\n"
            f"{status_emoji} **Your Status:** {status_text}\n"
            f"📈 **Today's Usage:** {usage_text} requests\n\n"
            f"✨ **What I Can Do:**\n"
            f"┣ 🔓 Bypass single or multiple shortened links\n"
            f"┣ 🎬 Animated processing with status updates\n"
            f"┣ 🔗 Generate clickable download links\n"
            f"┣ 💎 Premium subscription system\n"
            f"┣ 📊 Advanced usage tracking\n"
            f"┣ 🛡️ Anti-spam & rate limiting\n"
            f"┣ 🎨 Beautiful formatted results\n"
            f"┗ ⚡ Lightning fast processing\n\n"
            f"🎮 **Available Commands:**\n"
            f"┣ `/by <link>` - Bypass single link\n"
            f"┣ `/by <link1>, <link2>` - Bypass multiple links\n"
            f"┣ `/help` - Show detailed help guide\n"
            f"┣ `/stats` - View your statistics\n"
            f"┣ `/commands` - Show all commands\n"
            f"┗ Click buttons below for quick access!\n\n"
            f"💎 **Premium Benefits:**\n"
            f"┣ ♾️ Unlimited daily requests\n"
            f"┣ ⚡ Priority processing queue\n"
            f"┣ 💬 Private chat access\n"
            f"┣ 🎁 Exclusive features\n"
            f"┗ 👑 VIP support\n\n"
            f"🔥 **Join our community & get premium access!**\n"
            f"💰 **Price:** Just ₹25 for 30 days unlimited access!\n\n"
            f"⚡ **Developer:** {make_clickable_link('Contact Here', 'http://t.me/M4U_Admin_Bot')}\n"
            f"📢 **Updates:** {make_clickable_link('Malli4U Official', 'https://t.me/Malli4U_Official2')}"
        )
        
        await safe_edit_message(bot, message.chat.id, message.id, welcome_text, keyboard)
    
    await callback_query.answer()

# Sudo Commands (Owner only)
@Client.on_message(filters.command("addsudo") & filters.user(ADMIN_ID))
async def handle_add_sudo(bot: Client, message: Message):
    if len(message.command) != 2:
        return await message.reply("❌ Usage: `/addsudo <user_id>`")
    
    try:
        user_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid user ID format.")
    
    if user_manager.add_sudo(user_id):
        await message.reply(f"✅ User {user_id} promoted to sudo admin!")
        await safe_send_message(
            bot,
            user_id,
            "👑 **You are now a Sudo Admin!**\n\nThey now have owner-like privileges (e.g., add/remove filters, manage users)."
        )
    else:
        await message.reply(f"ℹ️ User {user_id} is already a sudo admin.")

@Client.on_message(filters.command("remsudo") & filters.user(ADMIN_ID))
async def remove_sudo_user(bot: Client, message: Message):
    if len(message.command) != 2:
        return await message.reply("❌ Usage: `/remsudo <user_id>`")
    
    try:
        user_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ Invalid user ID format.")
    
    if user_manager.remove_sudo(user_id):
        await message.reply(f"✅ User {user_id} removed from sudo admins.")
        await safe_send_message(
            bot,
            user_id,
            "ℹ️ Your sudo admin access has been removed.\n\nYou can no longer use admin commands."
        )
    else:
        await message.reply(f"ℹ️ User {user_id} is not a sudo admin.")

@Client.on_message(filters.command("sudoerslist") & (filters.user(ADMIN_ID) | filters.user(user_manager.is_sudo)))
async def list_sudoers(bot: Client, message: Message):
    sudo_list = user_manager.get_sudoers()
    if not sudo_list:
        await message.reply("**No sudo admins yet.**")
        return
    
    text = "**Sudo Admins:**\n"
    for uid in sudo_list:
        text += f"• `{uid}`\n"
    await message.reply(text, parse_mode=ParseMode.MARKDOWN)

# Admin Commands (Now allow sudo)
def is_authorized(user_id):
    return user_id == ADMIN_ID or user_manager.is_sudo(user_id)

@Client.on_message(filters.command("addpre") & filters.private)  # Or group
async def add_premium_user(bot: Client, message: Message):
    user_id = message.from_user.id
    if not is_authorized(user_id):
        await message.reply("**Unauthorized! Only owner or sudo admins can do this.**")
        return
    # ... rest of command

@Client.on_message(filters.command("banuser") & filters.private)  # Or group
async def ban_user(bot: Client, message: Message):
    user_id = message.from_user.id
    if not is_authorized(user_id):
        await message.reply("**Unauthorized! Only owner or sudo admins can do this.**")
        return
    # ... rest of command

# Initialization tasks
async def start_tasks():
    if await init_user_client():
        print("[DEBUG] Bypass handler initialized successfully")
        print("[DEBUG] Enhanced animation system activated")
        print("[DEBUG] Multi-link support enabled")
        print("[DEBUG] Clickable links system enabled")
        print("[DEBUG] SIMPLIFIED start system activated")
        print("[DEBUG] Error handling system active")
        print("[DEBUG] Auto-delete system enabled")
        print("[DEBUG] All systems operational")
    else:
        print("[DEBUG] Failed to initialize user client")

async def check_premium_expiry():
    while True:
        try:
            now = datetime.now().timestamp()
            expired = []
            for doc in db.premium.find({'expiry': {'$lt': now}}):
                expired.append(doc['_id'])
                db.premium.delete_one({'_id': doc['_id']})
                print(f"[DEBUG] Expired premium for user {doc['_id']}")
            
            for uid in expired:
                await safe_send_message(
                    bot_instance,
                    int(uid),
                    "⏰ **Premium Subscription Expired**\n\n"
                    "Your premium subscription has expired.\n\n"
                    "🔄 You're now on the free plan with 3 daily requests.\n\n"
                    "💎 **Renew Premium:** @M4U_Admin_Bot"
                )
            await asyncio.sleep(24 * 60 * 60)
        except Exception as e:
            print(f"[DEBUG] Error in premium expiry checker: {e}")
            await asyncio.sleep(3600)

print("[DEBUG] Enhanced Bypass module loaded with MULTI-LINK SUPPORT!")
