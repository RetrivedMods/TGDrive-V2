import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import config
from utils.logger import Logger
from pathlib import Path

logger = Logger(__name__)

START_CMD = """🚀 **Welcome to FileUpload Bot!**

Welcome to the **FileUpload** Bot! You can upload files directly to your **File Uploader** platform via this bot.

✨ **Commands:**
/set_folder - Set the folder for file uploads  
/current_folder - Check your current upload folder

📤 **How to upload files:**  
Simply send a file to this bot and it will be uploaded to your **FileUpload** platform.  
You can also set a folder for file uploads using the `/set_folder` command.

🔗 **View your uploaded files:**  
[Click here to access your uploaded files](https://zany-leonie-thunderlinks-0733fa02.koyeb.app/?path=/)  

Read more about **The Uploader's Bot Mode** in our [GitHub repository](https://github.com/RetrivedMods.TGDive).
"""

SET_FOLDER_PATH_CACHE = {}  # Cache to store folder path for each folder id
DRIVE_DATA = None
BOT_MODE = None

session_cache_path = Path(f"./cache")
session_cache_path.parent.mkdir(parents=True, exist_ok=True)

main_bot = Client(
    name="main_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.MAIN_BOT_TOKEN,
    sleep_threshold=config.SLEEP_THRESHOLD,
    workdir=session_cache_path,
)


@main_bot.on_message(
    filters.command(["start", "help"])
    & filters.private
    & filters.user(config.TELEGRAM_ADMIN_IDS),
)
async def start_handler(client: Client, message: Message):
    await message.reply_text(START_CMD)


@main_bot.on_message(
    filters.command("set_folder")
    & filters.private
    & filters.user(config.TELEGRAM_ADMIN_IDS),
)
async def set_folder_handler(client: Client, message: Message):
    global SET_FOLDER_PATH_CACHE, DRIVE_DATA

    while True:
        try:
            folder_name = await message.ask(
                "🗂️ Send the folder name where you want to upload files\n\n/cancel to cancel",
                timeout=60,
                filters=filters.text,
            )
        except asyncio.TimeoutError:
            await message.reply_text("⏰ Timeout! Please use /set_folder to try again.")
            return

        if folder_name.text.lower() == "/cancel":
            await message.reply_text("❌ Folder setting cancelled.")
            return

        folder_name = folder_name.text.strip()
        search_result = DRIVE_DATA.search_file_folder(folder_name)

        # Get folders from search result
        folders = {}
        for item in search_result.values():
            if item.type == "folder":
                folders[item.id] = item

        if len(folders) == 0:
            await message.reply_text(f"❗ No folder found with the name '{folder_name}'")
        else:
            break

    buttons = []
    folder_cache = {}
    folder_cache_id = len(SET_FOLDER_PATH_CACHE) + 1

    for folder in search_result.values():
        path = folder.path.strip("/")
        folder_path = "/" + ("/" + path + "/" + folder.id).strip("/")
        folder_cache[folder.id] = (folder_path, folder.name)
        buttons.append(
            [
                InlineKeyboardButton(
                    folder.name,
                    callback_data=f"set_folder_{folder_cache_id}_{folder.id}",
                )
            ]
        )
    SET_FOLDER_PATH_CACHE[folder_cache_id] = folder_cache

    await message.reply_text(
        "🔹 **Select the folder where you want to upload files**",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@main_bot.on_callback_query(
    filters.user(config.TELEGRAM_ADMIN_IDS) & filters.regex(r"set_folder_")
)
async def set_folder_callback(client: Client, callback_query: Message):
    global SET_FOLDER_PATH_CACHE, BOT_MODE

    folder_cache_id, folder_id = callback_query.data.split("_")[2:]

    folder_path_cache = SET_FOLDER_PATH_CACHE.get(int(folder_cache_id))
    if folder_path_cache is None:
        await callback_query.answer("❗ Request expired. Please use /set_folder again.")
        await callback_query.message.delete()
        return

    folder_path, name = folder_path_cache.get(folder_id)
    del SET_FOLDER_PATH_CACHE[int(folder_cache_id)]
    BOT_MODE.set_folder(folder_path, name)

    await callback_query.answer(f"✅ Folder successfully set to: {name}")
    await callback_query.message.edit(
        f"✅ Folder successfully set to: {name}\n\nNow you can send files to this bot and they will be uploaded to this folder."
    )


@main_bot.on_message(
    filters.command("current_folder")
    & filters.private
    & filters.user(config.TELEGRAM_ADMIN_IDS),
)
async def current_folder_handler(client: Client, message: Message):
    global BOT_MODE

    await message.reply_text(f"📂 Current Folder: {BOT_MODE.current_folder_name}")


# Handling when any file is sent to the bot
@main_bot.on_message(
    filters.private
    & filters.user(config.TELEGRAM_ADMIN_IDS)
    & (
        filters.document
        | filters.video
        | filters.audio
        | filters.photo
        | filters.sticker
    )
)
async def file_handler(client: Client, message: Message):
    global BOT_MODE, DRIVE_DATA

    copied_message = await message.copy(config.STORAGE_CHANNEL)
    file = (
        copied_message.document
        or copied_message.video
        or copied_message.audio
        or copied_message.photo
        or copied_message.sticker
    )

    DRIVE_DATA.new_file(
        BOT_MODE.current_folder,
        file.file_name,
        copied_message.id,
        file.file_size,
    )

    # Preparing the success message with detailed file information
    success_message = f"""
    ✅ **File Uploaded Successfully to Your Homie Uploader!**

    📄 **File Name:** {file.file_name}
    🗂️ **Folder:** {BOT_MODE.current_folder_name}
    📏 **File Size:** {file.file_size / 1024:.2f} KB
    📂 **File Type:** {file.mime_type}

    🔗 **Click below to view the uploaded file:**
    [View File Here](https://jolly-lobster-thunderlinks-43a7df8c.koyeb.app/)

    🎉 Your file has been successfully uploaded to **Homie Uploader**! Enjoy sharing your content! 🎉
    """

    # Send success message after deletion of the original message
    await message.delete()
    await message.reply_text(success_message)


async def start_bot_mode(d, b):
    global DRIVE_DATA, BOT_MODE
    DRIVE_DATA = d
    BOT_MODE = b

    logger.info("Starting Main Bot")
    await main_bot.start()

    await main_bot.send_message(
        config.STORAGE_CHANNEL, "Main Bot Started -> Homie Uploader Bot Mode Enabled"
    )
    logger.info("Main Bot Started")
    logger.info("Homie Uploader Bot Mode Enabled")
    
