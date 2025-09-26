from pyrogram import filters
from config import OWNER_ID  # Your super sudo

@app.on_message(filters.command("sudo") & filters.private)  # Or group if needed
async def sudo_handler(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ Unauthorized!")
    
    args = message.text.split()[1:]
    if not args:
        return await message.reply("Usage: /sudo add <user_id> | remove <user_id> | list")
    
    subcmd = args[0].lower()
    if subcmd == "add" and len(args) > 1:
        try:
            uid = int(args[1])
            if uid == OWNER_ID:
                return await message.reply("⚠️ Can't add the super sudo!")
            user_manager.add_admin(uid)
            await message.reply(f"✅ Added {uid} as admin.")
        except ValueError:
            await message.reply("❌ Invalid ID!")
    
    elif subcmd == "remove" and len(args) > 1:
        try:
            uid = int(args[1])
            if uid == OWNER_ID:
                return await message.reply("⚠️ Can't remove the super sudo!")
            user_manager.remove_admin(uid)
            await message.reply(f"✅ Removed {uid}.")
        except ValueError:
            await message.reply("❌ Invalid ID!")
    
    elif subcmd == "list":
        admins = user_manager.get_admins()
        text = "Admins:\n" + "\n".join(map(str, admins)) if admins else "None"
        await message.reply(text)
    
    else:
        await message.reply("Invalid: add/remove/list")
