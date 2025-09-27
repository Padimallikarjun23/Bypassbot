import os
import asyncio
import logging
from datetime import datetime
from aiohttp import web
from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.types import BotCommand
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, PORT
from plugins.bypass_handler import start_tasks, set_bot_instance, check_premium_expiry

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class BypassBot(Client):
    def __init__(self):
        super().__init__(
            name="bypass_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins=dict(root="plugins"),
            workers=4,
            in_memory=True
        )
        self.logger = logger
        self.uptime = None

    async def start(self):
        try:
            await super().start()
            me = await self.get_me()
            self.username = me.username
            self.uptime = datetime.now()

            # Set bot commands for menu
            commands = [
                BotCommand("start", "Start the bot 🚀"),
                BotCommand("help", "Get help about using the bot ℹ️"),
                BotCommand("by", "Bypass a shortened URL 🔄"),
                BotCommand("stats", "Check your usage statistics 📊"),
                BotCommand("commands", "List all available commands 📋"),
                BotCommand("addpre", "Add premium user (admin only) 💎"),
                BotCommand("removepre", "Remove premium user (admin only) 🛑"),
                BotCommand("addsudo", "Add sudo admin (owner only) 👑"),
                BotCommand("remsudo", "Remove sudo admin (owner only) 🛑"),
                BotCommand("sudoers", "List sudo admins (owner only) 📋"),
                BotCommand("ban", "Ban a user (admin only) 🚫"),
                BotCommand("unban", "Unban a user (admin only) ✅"),
                BotCommand("broadcast", "Send message to all users (admin only) 📢")
            ]
            await self.set_bot_commands(commands)
            logger.info("Bot commands set in menu")

            # Initialize plugins
            set_bot_instance(self)
            await start_tasks()
            logger.info("✅ Plugins initialized successfully")

            # Start premium expiry checker
            asyncio.create_task(check_premium_expiry())
            logger.info("✅ Premium expiry checker started")

            # Start web server for keep-alive (e.g., Railway)
            async def handle_ping(request):
                return web.Response(text="Bot is alive!")
            app = web.Application()
            app.add_routes([web.get('/ping', handle_ping)])
            runner = web.AppRunner(app)
            await runner.setup()
            await web.TCPSite(runner, "0.0.0.0", PORT).start()
            logger.info(f"Web server started on port {PORT}")

            # Send startup notification to admin
            startup_message = (
                f"🚀 **Bypass Bot Started!**\n\n"
                f"**Bot Username:** @{me.username}\n"
                f"**Bot ID:** `{me.id}`\n"
                f"**Status:** Online ✅\n"
                f"**Uptime:** {self.uptime.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"💎 **Premium Settings:**\n"
                f"┣ **Price:** ₹25 per month\n"
                f"┣ **Free Limit:** 3 links/day\n"
                f"┣ **Premium:** Unlimited\n"
                f"┗ **MongoDB:** Connected\n\n"
                f"👨‍💻 **Developer:** @Malli4U_Admin_Bot\n"
                f"📞 **Support:** @M4U_Admin_Bot\n\n"
                f"🎉 **All systems operational!**"
            )
            await self.send_message(
                chat_id=ADMIN_ID,
                text=startup_message,
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info("Startup notification sent to admin")

        except Exception as e:
            if "AUTH_KEY_DUPLICATED" in str(e):
                logger.error("Session conflict detected! Make sure the bot is not running elsewhere.")
                raise SystemExit(1)
            logger.error(f"Failed to start bot: {e}")
            raise

    async def stop(self):
        try:
            await self.send_message(
                chat_id=ADMIN_ID,
                text="🔴 **Bot Shutting Down**\n\nThe bot has been stopped successfully.",
                parse_mode=ParseMode.MARKDOWN
            )
            await super().stop()
            logger.info("Bot stopped successfully")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

def main():
    print("=" * 60)
    print("🚀 Starting Malli4U Bypass Bot")
    print("=" * 60)
    print(f"💎 Premium: ₹25 for unlimited access")
    print(f"🆓 Free: 3 links per day")
    print(f"👨‍💻 Developer: @Malli4U_Admin_Bot")
    print(f"📞 Support: @M4U_Admin_Bot")
    print("=" * 60)

    try:
        # Validate configuration
        if not BOT_TOKEN:
            print("❌ BOT_TOKEN is required!")
            return
        if not API_ID or not API_HASH:
            print("❌ API_ID and API_HASH are required!")
            return
        from config import MONGO_URI
        if not MONGO_URI:
            print("❌ MONGO_URI is required!")
            return

        print("✅ Configuration validation passed")
        print("🤖 Initializing bot...")

        # Create and run bot
        app = BypassBot()
        print("🎯 Starting bot...")
        app.run()

    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user (Ctrl+C)")
    except Exception as e:
        print(f"❌ Critical Error: {e}")
        logger.error(f"Critical error in main: {e}")

if __name__ == "__main__":
    main()
