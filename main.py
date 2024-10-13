import asyncio
import signal
import logging
import platform
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters, CallbackQueryHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import pymongo
from datetime import datetime, timezone
from bson import ObjectId
from keepalive import keep_alive
from dotenv import load_dotenv
import os


load_dotenv()


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING) 
logger = logging.getLogger(__name__)

# Configuration
Token = os.getenv("TELEGRAM_BOT_TOKEN")
MongoDB = os.getenv("MONGODB_URI")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))


client = pymongo.MongoClient(MongoDB, maxPoolSize=50, waitQueueTimeoutMS=2500)
db = client.Telegram
assignment_collection = db.Files
users_collection = db.Users


ASK_TITLE, ASK_DOCUMENT = range(2)


timetable = {
    "Monday": [
        "9:00 AM - 9:55 AM: Web Programming",
        "9:55 AM - 10:50 AM: AI",
        "10:50 AM - 11:00 AM: Break",
        "11:00 AM - 11:55 AM: Disaster Management",
        "11:55 AM - 12:40 PM: Lunch Break",
        "12:40 PM - 1:35 PM: Web Programming",
        "1:35 PM - 2:30 PM: AI",
        "2:30 PM - 2:40 PM: Break",
        "2:40 PM - 3:35 PM: Honours",
        "3:35 PM - 4:30 PM: Industrial Safety Engineering"
    ],
    "Tuesday": [
        "9:00 AM - 11:55 AM: Compiler Lab",
        "11:55 AM - 12:40 PM: Lunch Break",
        "12:40 PM - 1:35 PM: Web Programming",
        "1:35 PM - 2:30 PM: Minor",
        "2:30 PM - 2:40 PM: Break",
        "2:40 PM - 3:35 PM: Disaster Management",
        "3:35 PM - 4:30 PM: AI"
    ],
    "Wednesday": [
        "9:00 AM - 11:55 AM: Seminar",
        "11:55 AM - 12:40 PM: Lunch Break",
        "12:40 PM - 1:35 PM: Web Programming",
        "1:35 PM - 2:30 PM: AI",
        "2:30 PM - 2:40 PM: Break",
        "2:40 PM - 3:35 PM: Honours",
        "3:35 PM - 4:30 PM: Industrial Safety Engineering"
    ],
    "Thursday": [
        "9:00 AM - 9:55 AM: AI",
        "9:55 AM - 10:50 AM: Industrial Safety Engineering",
        "10:50 AM - 11:00 AM: Break",
        "11:00 AM - 11:55 AM: Minor",
        "11:55 AM - 12:40 PM: Lunch Break",
        "12:40 PM - 1:35 PM: Disaster Management",
        "1:35 PM - 2:30 PM: Honours",
        "2:30 PM - 2:40 PM: Break",
        "2:40 PM - 3:35 PM: Industrial Safety Engineering",
        "3:35 PM - 4:30 PM: Minor"
    ],
    "Friday": [
        "9:00 AM - 4:30 PM: Project"
    ]
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.message.from_user
        user_id = user.id
        first_name = user.first_name
        last_name = user.last_name or ''
        username = user.username or ''

        if not users_collection.find_one({"user_id": user_id}):
            users_collection.insert_one({
                "user_id": user_id,
                "first_name": first_name,
                "last_name": last_name,
                "username": username,
                "block":0
            })
        full_name = f"{first_name} {last_name}".strip()
        welcome_message = f"Welcome to the Assignment Bot, {full_name}! Use /help to see available commands."
        await update.message.reply_text(welcome_message)
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await update.message.reply_text("An error occurred. Please try again later.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.message.from_user
        user_id = user.id
        first_name = user.first_name
        last_name = user.last_name or ''
        username = user.username or ''

        if not users_collection.find_one({"user_id": user_id}):
            users_collection.insert_one({
                "user_id": user_id,
                "first_name": first_name,
                "last_name": last_name,
                "username": username,
                "block":0
            })
        await update.message.reply_text(
            "/start                     - To start the bot\n"
            "/help                      - To get help\n"
            "/works                   - To get the assignments/record/notes\n"
            "/timetable            - To get the timetable\n"
            "/addassignment - To add an assignment (Admin only)\n"
        )
    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await update.message.reply_text("An error occurred. Please try again later.")

async def assignments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        if not users_collection.find_one({"user_id": user.id}):
            users_collection.insert_one({
                "user_id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name or '',
                "username": user.username or '',
                "block":0
        })
        user_info = f"User ID: {user.id}, Username: {user.username}, Name: {user.full_name}"
        logger.info(f"Assignment request from: {user_info}")
        if users_collection.find_one({"user_id": user.id})['block'] == 1:
            await update.message.reply_text("Some issues with your account. Please contact the admin @levi_4225")
            logger.info(f"Blocked user tried to access assignments: {user_info}")
            return
        assignments = assignment_collection.find().sort('timestamp', -1)
        
        if assignment_collection.count_documents({}) > 0:
            keyboard = [
                [InlineKeyboardButton(assignment['title'], callback_data=str(assignment['_id']))]
                for assignment in assignments
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Select a file to download:", reply_markup=reply_markup)
        else:
            await update.message.reply_text("No files available.")
    except Exception as e:
        logger.error(f"Error in assignments command: {e}")
        await update.message.reply_text("An error occurred. Please try again later.")

async def send_assignment_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_info = f"User ID: {user.id}, Username: {user.username}, Name: {user.full_name}"
    assignment_id = query.data
    try:
        assignment = assignment_collection.find_one({"_id": ObjectId(assignment_id)})
        if users_collection.find_one({"user_id": user.id})['block'] == 1:
            logger.info(f"File not sent to {user_info} - Account blocked")
            await update.message.reply_text("Some issues with your account. Please contact the admin @levi_4225")
            return
        if assignment:
            file_id = assignment['file_url']
            file_title = assignment['title']
            sent_file = await context.bot.send_document(chat_id=query.message.chat_id, document=file_id)
            logger.info(f"File sent: '{file_title}' to {user_info}")
        else:
            await query.message.reply_text("Sorry, the assignment could not be found.")
            logger.warning(f"Failed to send file to {user_info} - Assignment not found (ID: {assignment_id})")
    except Exception as e:
        logger.error(f"Error sending assignment file: {e}")
        await query.message.reply_text("An error occurred while sending the file. Please try again later.")

async def timetable_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.args:
            day = context.args[0].capitalize() 
        else:
            day = datetime.now().strftime('%A')  
        day_timetable = timetable.get(day, [])
        if day_timetable:
            timetable_text = f"{day}'s timetable:\n" + "\n".join(day_timetable)
        else:
            timetable_text = f"No timetable available for {day}."
        await update.message.reply_text(timetable_text)
    except Exception as e:
        logger.error(f"Error in timetable command: {e}")
        await update.message.reply_text("An error occurred. Please try again later.")

async def addassignment_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized to add assignments.")
        return ConversationHandler.END

    await update.message.reply_text("Please enter the title of the assignment:")
    return ASK_TITLE

async def ask_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['assignment_title'] = update.message.text
    await update.message.reply_text("Now, please upload the document for the assignment:")
    return ASK_DOCUMENT

async def save_assignment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        document = update.message.document
        title = context.user_data['assignment_title']
        user_id = update.message.from_user.id

        if document:
            file_id = document.file_id
            assignment_collection.insert_one({
                'title': title,
                'file_url': file_id,
                'uploaded_by': user_id,
                'timestamp': datetime.now(timezone.utc) 
            })
            await update.message.reply_text(f"Assignment '{title}' added successfully.")
            users = users_collection.find()
            for user in users:
                try:
                    await context.bot.send_message(chat_id=user['user_id'], text=f"Admin uploaded a new assignment: {title} Please check the /works for more details.")
                except Exception as e:
                    logger.error(f"Failed to send message to {user['user_id']}: {e}")
        else:
            await update.message.reply_text("No document uploaded. Assignment addition canceled.")
    except Exception as e:
        logger.error(f"Error in save_assignment: {e}")
        await update.message.reply_text("An error occurred while saving the assignment. Please try again.")
    finally:
        context.user_data.clear()
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Assignment creation canceled.")
    return ConversationHandler.END

async def shutdown(signal, loop):
    """Cleanup tasks tied to the service's shutdown."""
    logger.info(f"Received exit signal {signal.name}...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    [task.cancel() for task in tasks]

    logger.info(f"Cancelling {len(tasks)} outstanding tasks")
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()

def handle_exception(loop, context):
    msg = context.get("exception", context["message"])
    logger.error(f"Caught exception: {msg}")
    logger.info("Shutting down...")
    asyncio.create_task(shutdown(signal.SIGTERM, asyncio.get_running_loop()))

def main():
    logger.info("Bot is starting")
    
    if platform.system() != 'Windows':
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        signals = (signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(shutdown(s, loop))
            )
    else:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.set_exception_handler(handle_exception)

    keep_alive()
    
    app = Application.builder().token(Token).build()


    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("works", assignments))
    app.add_handler(CommandHandler("timetable", timetable_command))
    
    add_assignment_conv = ConversationHandler(
        entry_points=[CommandHandler('addassignment', addassignment_start)],
        states={
            ASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_document)],
            ASK_DOCUMENT: [MessageHandler(filters.Document.ALL, save_assignment)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    app.add_handler(add_assignment_conv)
    app.add_handler(CallbackQueryHandler(send_assignment_file))

    try:
        app.run_polling(poll_interval=3)
    except Exception as e:
        logger.error(f"Error in main function: {e}")
    finally:
        client.close()  # Close MongoDB connection when the bot stops

if __name__ == "__main__":
    main()