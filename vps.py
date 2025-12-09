import os
import asyncio
import shutil
from zipfile import ZipFile
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters
)

# REPLACE THIS WITH YOUR NEW TOKEN AFTER REVOKING THE OLD ONE
TOKEN = "8103869618:AAH6edVV_OQsXSBRFN4mSPq2jTFUgI1V6kg" 
ALLOWED_USERS = [7613349080]

# Initial directory
current_dir = os.getcwd()

# ------------------ HELPERS ------------------
async def run_cmd(cmd):
    """Runs shell commands asynchronously so the bot doesn't freeze."""
    try:
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=current_dir
        )
        stdout, stderr = await process.communicate()
        
        output = stdout.decode().strip()
        error = stderr.decode().strip()
        
        if output and error:
            return f"{output}\n\nError:\n{error}"
        return output if output else error
    except Exception as e:
        return str(e)

def zip_dir(path, zip_name):
    """Zips a directory."""
    with ZipFile(zip_name, "w") as z:
        for root, _, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f)
                # Prevent zipping the zip file itself if it's in the same folder
                if f == zip_name:
                    continue
                arc = os.path.relpath(fp, path)
                z.write(fp, arc)

def check_auth(user_id):
    return user_id in ALLOWED_USERS

# ------------------ /add (step 1) ------------------
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        return

    context.user_data["await_file"] = True
    await update.message.reply_text(f"📥 Send a file to upload to:\n`{current_dir}`", parse_mode="Markdown")

# ------------------ /add (step 2: upload) ------------------
async def upload_after_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        return

    # Only accept file if user previously used /add
    if not context.user_data.get("await_file"):
        return await update.message.reply_text("❌ Use /add command first.")

    doc = update.message.document
    tg_file = await doc.get_file()

    # Security: Ensure we only get the filename, stripping any path traversal (../../)
    safe_filename = os.path.basename(doc.file_name)
    save_path = os.path.join(current_dir, safe_filename)
    
    await tg_file.download_to_drive(save_path)

    context.user_data["await_file"] = False  # Reset state
    await update.message.reply_text(f"✅ Saved: `{safe_filename}`", parse_mode="Markdown")

# ------------------ /get ------------------
async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        return

    context.user_data["await_file"] = False  # Cancel upload mode if active

    args = context.args
    if not args:
        return await update.message.reply_text("Usage: /get <filename> or /get .")

    name = " ".join(args) # Handle filenames with spaces

    if name == ".":
        wait_msg = await update.message.reply_text("🗜 Zipping folder...")
        zip_name = "folder_dump.zip"
        try:
            # Run blocking zip in a separate thread to not freeze bot
            await asyncio.to_thread(zip_dir, current_dir, zip_name)
            await update.message.reply_document(open(zip_name, "rb"))
            os.remove(zip_name) # Cleanup
        except Exception as e:
            await update.message.reply_text(f"Error zipping: {e}")
        finally:
            await wait_msg.delete()
        return

    # Normal file download
    path = os.path.join(current_dir, name)
    if not os.path.exists(path):
        return await update.message.reply_text("❌ File not found")
    
    if os.path.isdir(path):
        return await update.message.reply_text("❌ It's a directory. Use /get . inside it or zip it manually.")

    try:
        await update.message.reply_document(open(path, "rb"))
    except Exception as e:
        await update.message.reply_text(f"❌ Error sending file: {e}")

# ------------------ SHELL ------------------
async def shell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_dir

    if not check_auth(update.effective_user.id):
        return

    context.user_data["await_file"] = False # Cancel upload mode

    cmd = update.message.text.strip()

    # --- 'cd' Handling ---
    if cmd.startswith("cd "):
        try:
            target = cmd[3:].strip()
            # Resolve path relative to current_dir
            new_path = os.path.abspath(os.path.join(current_dir, target))
            
            if os.path.isdir(new_path):
                current_dir = new_path
                return await update.message.reply_text(f"📂 Changed to:\n`{current_dir}`", parse_mode="Markdown")
            else:
                return await update.message.reply_text("❌ Directory not found")
        except Exception as e:
            return await update.message.reply_text(f"❌ Error: {e}")

    # --- Shell Execution ---
    status_msg = await update.message.reply_text("⏳ Executing...")
    
    out = await run_cmd(cmd)
    
    await status_msg.delete()

    if not out:
        await update.message.reply_text("✅ Executed (No Output)")
    elif len(out) < 4000:
        # Telegram max message length is 4096
        await update.message.reply_text(f"```\n{out}\n```", parse_mode="Markdown")
    else:
        # If output is too long, send as text file
        with open("output.txt", "w", encoding="utf-8") as f:
            f.write(out)
        await update.message.reply_document(open("output.txt", "rb"), caption="Output too long, sent as file.")
        os.remove("output.txt") # Cleanup

# ------------------ MAIN ------------------
if __name__ == "__main__":
    if TOKEN == "YOUR_NEW_TOKEN_HERE":
        print("Error: You must set the TOKEN variable in the script.")
        exit()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("add", add))
    app.add_handler(MessageHandler(filters.Document.ALL, upload_after_add))
    app.add_handler(CommandHandler("get", get_file))
    # Handle text messages that are NOT commands (shell)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, shell))

    print("Bot is running...")
    app.run_polling()