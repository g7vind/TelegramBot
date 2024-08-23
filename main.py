from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters, CallbackQueryHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import pymongo
from datetime import datetime, timezone
from bson import ObjectId
from keepalive import keep_alive
from dotenv import load_dotenv
import os

keep_alive()

# Load environment variables from .env file
load_dotenv()

# Configuration
Token = os.getenv("TELEGRAM_BOT_TOKEN")
MongoDB = os.getenv("MONGODB_URI")

# Set up MongoDB client
client = pymongo.MongoClient(MongoDB)
db = client.Telegram
assignment_collection = db.Files
users_collection = db.Users  # Collection for storing user IDs

# List of admin user IDs
Admin = [1293507674, 5061560776]

# Conversation states
ASK_TITLE, ASK_DOCUMENT = range(2)

# Timetable data
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

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    first_name = user.first_name
    last_name = user.last_name or ''
    username = user.username or ''
    
    # Check if the user is already in the database
    if not users_collection.find_one({"user_id": user_id}):
        users_collection.insert_one({
            "user_id": user_id,
            "first_name": first_name,
            "last_name": last_name,
            "username": username
        })
    # Create a personalized welcome message
    full_name = f"{first_name} {last_name}".strip()
    welcome_message = f"Welcome to the Assignment Bot, {full_name}! Use /help to see available commands."
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start                     - To start the bot\n"
        "/help                      - To get help\n"
        "/works                   - To get the assignments/record/notes\n"
        "/timetable            - To get the timetable\n"
        "/addassignment - To add an assignment (Admin only)\n"
    )

async def assignments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    assignments = assignment_collection.find().sort('timestamp', -1)
    
    if assignment_collection.count_documents({}) > 0:
        # Create an inline keyboard for each assignment
        keyboard = [
            [InlineKeyboardButton(assignment['title'], callback_data=str(assignment['_id']))]
            for assignment in assignments
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Select a file to download:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("No files available.")

async def send_assignment_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Retrieve the assignment using the ID stored in callback_data
    assignment_id = query.data
    assignment = assignment_collection.find_one({"_id": ObjectId(assignment_id)})

    if assignment:
        # Use the file_id to get and send the file
        file_id = assignment['file_url']
        await context.bot.send_document(chat_id=query.message.chat_id, document=file_id)
    else:
        await query.message.reply_text("Sorry, the assignment could not be found.")

async def timetable_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        day = context.args[0].capitalize()  # Get the day from the command argument and capitalize it
    else:
        day = datetime.now().strftime('%A')  # Default to today's day if no argument is provided
    
    day_timetable = timetable.get(day, [])
    if day_timetable:
        timetable_text = f"{day}'s timetable:\n" + "\n".join(day_timetable)
    else:
        timetable_text = f"No timetable available for {day}."
    await update.message.reply_text(timetable_text)

async def addassignment_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in Admin:
        await update.message.reply_text("You are not authorized to add assignments.")
        return ConversationHandler.END

    await update.message.reply_text("Please enter the title of the assignment:")
    return ASK_TITLE

async def ask_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['assignment_title'] = update.message.text
    await update.message.reply_text("Now, please upload the document for the assignment:")
    return ASK_DOCUMENT

async def save_assignment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    title = context.user_data['assignment_title']
    user_id = update.message.from_user.id

    if document:
        file_id = document.file_id  # Store the file_id in MongoDB
        assignment_collection.insert_one({
            'title': title,
            'file_url': file_id,
            'uploaded_by': user_id,
            'timestamp': datetime.now(timezone.utc) 
        })
        await update.message.reply_text(f"Assignment '{title}' added successfully.")
        
        # Notify all users about the new assignment
        users = users_collection.find()
        for user in users:
            try:
                await context.bot.send_message(chat_id=user['user_id'], text=f"Admin uploaded a new assignment: {title} Please check the /works for more details.")
            except Exception as e:
                print(f"Failed to send message to {user['user_id']}: {e}")
    else:
        await update.message.reply_text("No document uploaded. Assignment addition canceled.")

    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Assignment creation canceled.")
    return ConversationHandler.END

# Main function to run the bot
if __name__ == "__main__":
    print("Bot is running")
    
    app = Application.builder().token(Token).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("works", assignments))
    app.add_handler(CommandHandler("timetable", timetable_command))
    
    # Conversation handler for adding assignments
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

    app.run_polling(poll_interval=3)
