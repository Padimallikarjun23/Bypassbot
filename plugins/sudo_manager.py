from pyrogram import Client, filters
from config import ADMIN_IDS
from plugins.user_manager import user_manager

# Only the main owner (first ADMIN_ID) can run /sudo
SUPER_SUDO_ID = ADMIN_IDS[0] if ADMIN_IDS else None

@Client.on_message(filters.command("sudo") & filters.private)
async def sudo_handler(client, message):
    user_id = message.from_user.id
    if SUPER_SUDO_ID is None or user_id != SUPER_SUDO_ID:
        await message.reply("❌ Unauthorized! Only the bot owner can use this.")
        return

    args = message.text.split()[1:]
    if not args:
        await message.reply("Usage: /sudo add <user_id> | remove <user_id> | list")
        return

    subcmd = args[0].lower()
    if subcmd == "add" and len(args) > 1:
        try:
            new_id = int(args[1])
            if user_manager.add_admin(new_id):
                await message.reply(f"✅ Added {new_id} as admin.")
            else:
                await message.reply(f"⚠️ {new_id} is already an admin.")
        except ValueError:
            await message.reply("❌ Invalid user ID! Must be a number.")

    elif subcmd == "remove" and len(args) > 1:
        try:
            rem_id = int(args[1])
            if user_manager.remove_admin(rem_id):
                await message.reply(f"✅ Removed {rem_id} from admins.")
            else:
                await message.reply(f"⚠️ {rem_id} is not an admin.")
        except ValueError:
            await message.reply("❌ Invalid user ID! Must be a number.")

    elif subcmd == "list":
        admins = user_manager.get_admins()
        admin_list = "\n".join(map(str, admins))
        await message.reply(f"👑 Current admins:\n{admin_list or 'None'}")

    else:
        await message.reply("Invalid subcommand! Use: add, remove, or list.")
