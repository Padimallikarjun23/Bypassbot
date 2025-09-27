import re
import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatAction, ParseMode
from pyrogram.errors import PeerIdInvalid, ChatAdminRequired, UserNotParticipant, FloodWait, MessageDeleteForbidden, MessageNotModified
from .user_manager import user_manager
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
    """Create a clickable markdown link"""
    safe_text = str(text).replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)')
    clean_url = str(url).strip()
    return f"[{safe_text}]({clean_url})"

def extract_multiple_links(text):
    """Extract multiple links from text - supports comma, space, and newline separation"""
    text = re.sub(r'^/by\s*|^!by\s*', '', text, flags=re.IGNORECASE).strip()
    urls = re.findall(r'https?://[^\s,\n]+', text)
    cleaned_urls = [re.sub(r'[,\.\)]+$', '', url) for url in urls if url]
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
    from database import db
    doc = db.season_store.find_one({'_id': key})
    return doc.get('season') if doc else None

async def save_season_store(key, season):
    """Save season to MongoDB"""
    from database import db
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
                f"\n\n⚡ **Powered by @Malli4U_Admin_Bot**\n"
                f"👤 **Requested by:** {req['user_id']}\n"
                f"⏰ **Time:** {datetime.now().strftime('%H:%M:%S')}"
            )
            
            await safe_send_message(bot_instance, group_id, formatted_text, original_msg_id)
            print(f"[DEBUG] Successfully sent multi-link bypass result with {len(link_pairs)} links")
            return
    
    # Handle single link response
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
                f"⚡ **Powered by @Malli4U_Admin_Bot**\n"
                f"🙍 **Requested by:** {req['user_id']}\n"
                f"⏰ **Time:** {datetime.now().strftime('%H:%M:%S')}"
            )
            
            await safe_send_message(bot_instance, group_id, formatted_text, original_msg_id)
            print("[DEBUG] Successfully sent formatted bypass message with clickable links")
            return
    
    # Fallback: Try to extract links and format with clickable links
    bypassed_links, title, size = extract_links_from_text_and_buttons(text, message.reply_markup)
    
    if not bypassed_links:
        await safe_send_message(
            bot_instance, 
            group_id, 
            "❌ **Bypass Failed**\n\nCould not process the bypass response. Please try again or contact support.\n\n🆘 **Support:** @M4U_Admin_Bot", 
            original_msg_id
        )
        return
    
    # Format message with clickable links
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
        clickable = make_clickable_link(link_name, link_url)
        formatted.append(f"**{i}.** {clickable}\n")
    
    formatted.append(f"\n⚡ **Powered by @Malli4U_Admin_Bot**\n👤 **Requested by:** {req['user_id']}\n⏰ **Time:** {datetime.now().strftime('%H:%M:%S')}")
    final_text = "\n".join(formatted)
    
    await safe_send_message(bot_instance, group_id, final_text, original_msg_id)
    print("[DEBUG] Successfully sent formatted message with ALL CLICKABLE LINKS")

# Main Bypass Handler with Multi-Link Support
@Client.on_message(filters.command(["by", "!by"]))
async def handle_by(bot: Client, message: Message):
    global bot_instance
    bot_instance = bot
    
    if not message.from_user:
        return await message.reply("❌ Cannot process message from anonymous user.")

    # Check if the command has link argument(s)
    if len(message.command) < 2:
        return await message.reply(
            "❌ **Usage:**\n\n"
            "**Single Link:** `/by <link>`\n"
            "**Multiple Links:** `/by <link1>, <link2>, <link3>`\n\n"
            "📝 **Example:** `/by https://bit.ly/link1, https://tinyurl.com/link2`"
        )
    
    # Extract multiple links from the message text
    text = message.text.replace("/by", "").replace("!by", "").strip()
    urls = extract_multiple_links(message.text)
    
    if not urls:
        return await message.reply(
            "❌ **Invalid Link Format**\n\n"
            "Please provide valid link(s) after the `/by` command.\n\n"
            "📝 **Examples:**\n"
            "┣ `/by https://bit.ly/example`\n"
            "┣ `/by https://bit.ly/link1, https://tinyurl.com/link2`\n"
            "┗ `/by https://short.link/abc https://ouo.io/xyz`",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Block softurl.in links
    if any("softurl.in" in url.lower() for url in urls):
        return await message.reply(
            "⚠️ **Softurl.in links are not supported!**\n\n"
            "These links cannot be bypassed for security reasons.\n\n"
            "📞 Contact admin for more information: @M4U_Admin_Bot"
        )
    
    uid = str(message.from_user.id)
    chat_type = message.chat.type
    
    # Permission check with better error handling
    if chat_type == "private":
        if not (user_manager.is_premium(uid) or user_manager.is_admin(message.from_user.id)):
            return await message.reply(
                "❌ **Private Chat Access Restricted**\n\n"
                "Only premium users and admin can use this bot in private chat.\n\n💎 **Get Premium:** @M4U_Admin_Bot", 
                parse_mode=ParseMode.MARKDOWN
            )
        group_id = message.chat.id
    else:
        try:
            if message.chat.id != TARGET_GROUP_ID:
                return
            group_id = TARGET_GROUP_ID
        except Exception as e:
            print(f"[DEBUG] Error checking group ID: {e}")
            return
    
    # Rate limit for free users (counts as 1 request regardless of number of links)
    if not (user_manager.is_premium(uid) or user_manager.is_admin(message.from_user.id)):
        if user_manager.get_daily_usage(message.from_user.id) >= 3:
            return await message.reply(
                "⚠️ **Daily Limit Reached!** 😔\n\n"
                "You have reached your daily limit of **3 requests**.\n\n"
                "💎 **Get unlimited access with Premium!**\n"
                "┣ ♾️ Unlimited daily requests\n"
                "┣ ⚡ Priority processing\n"
                "┣ 🎬 Premium animations\n"
                "┣ 🔗 Multi-link support\n"
                "┣ 🔗 Enhanced clickable links\n"
                "┣ 💬 Private chat access\n"
                "┗ 👑 VIP support\n\n"
                "💰 **Price:** Only ₹25 for 30 days\n"
                "📞 **Contact:** @Malli4U_Admin_Bot", 
                parse_mode=ParseMode.MARKDOWN
            )
    
    # Extract season
    season = re.search(r"season\s*\d+", message.text, re.IGNORECASE)
    if season:
        key = f"{message.chat.id}:{message.from_user.id}"
        await save_season_store(key, season.group(0))
    
    await message.reply_chat_action(ChatAction.TYPING)
    
    # Ensure user client connected
    if not getattr(user_client, "is_connected", False):
        if not await init_user_client():
            return await message.reply(
                "❌ **Service Unavailable**\n\n"
                "Could not connect to bypass service. Please try again later.\n\n🆘 **Support:** @M4U_Admin_Bot", 
                parse_mode=ParseMode.MARKDOWN
            )
    
    # Join multiple links with spaces for DD bypass bot
    links_str = " ".join(urls)
    link_count = len(urls)
    
    # Create initial status message with animation
    status_msg = await message.reply(
        f"🚀 **Initiating bypass process for {link_count} link(s)...**\n\n⏱️ **Status:** Starting...", 
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        sent = await user_client.send_message(BYPASS_BOT_USERNAME, f"B {links_str}")
        print(f"[DEBUG] Sent multi-link bypass request with message ID: {sent.id} for {link_count} links")
    except Exception as e:
        print(f"[DEBUG] Error sending message: {e}")
        await status_msg.delete()
        return await message.reply(
            "❌ **Request Failed**\n\n"
            "Could not send bypass request. Please try again later.\n\n🆘 **Support:** @M4U_Admin_Bot", 
            parse_mode=ParseMode.MARKDOWN
        )
    
    if not (user_manager.is_premium(uid) or user_manager.is_admin(message.from_user.id)):
        user_manager.increment_usage(message.from_user.id)
    
    # Store all original links as a single string (space-separated)
    pending_bypass_requests[sent.id] = {
        "group_id": group_id,
        "user_id": message.from_user.id,
        "original_msg_id": message.id,
        "original_link": links_str,  # All links as space-separated string
        "link_count": link_count,
        "time_sent": asyncio.get_event_loop().time(),
        "status_msg": status_msg,
        "chat_type": chat_type
    }
    
    # Start animation task
    asyncio.create_task(animate_processing_message(status_msg, 20))
    
    print(f"[DEBUG] Added pending multi-link request: {sent.id} with {link_count} links")

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
            expired = user_manager.check_premium_expiry()
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
