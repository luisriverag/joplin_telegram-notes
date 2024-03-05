from telegram import Update, File
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
import requests
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve configuration values from environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAMBOT_ML_TOKEN')
JOPLIN_TOKEN = os.getenv('JOPLIN_TOKEN')
JOPLIN_PORT = os.getenv('JOPLIN_PORT', '41184')

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Hello! Send me a note, photo, or file to save to Joplin.')

def save_note_to_joplin(title, body):
    url = f'http://localhost:{JOPLIN_PORT}/notes?token={JOPLIN_TOKEN}'
    data = {'title': title, 'body': body}
    response = requests.post(url, json=data)
    if response.status_code == 200:
        return "Successfully saved in Joplin!"
    else:
        return "Failed to save."

def handle_message(update: Update, context: CallbackContext) -> None:
    note_content = update.message.text
    result = save_note_to_joplin('Telegram Note', note_content)
    update.message.reply_text(result)

def search_notes_in_joplin(query):
    url = f'http://localhost:{JOPLIN_PORT}/search?query={query}&token={JOPLIN_TOKEN}'
    response = requests.get(url)
    if response.status_code == 200 and response.json().get('items'):
        notes = response.json().get('items')
        messages = ['Here are the notes I found:']
        for note in notes[:5]:  # Show up to 5 results for brevity
            messages.append(f"- {note.get('title')}: {note.get('id')}")
        return "\n".join(messages)
    else:
        return "No notes found or failed to search."

def handle_search(update: Update, context: CallbackContext) -> None:
    query = ' '.join(context.args)
    if not query:
        update.message.reply_text('Please provide a search query after the /search command.')
        return
    result = search_notes_in_joplin(query)
    update.message.reply_text(result)

def handle_photo(update: Update, context: CallbackContext) -> None:
    photo = update.message.photo[-1]  # Get the highest resolution photo
    photo_file = context.bot.getFile(photo.file_id)
    # Save the photo temporarily
    photo_path = f"{photo.file_id}.jpg"
    photo_file.download(photo_path)
    # For simplicity, we're embedding the image in the note body as a markdown image link
    note_title = "Photo from Telegram"
    note_body = f"![Image](file:///{os.path.abspath(photo_path)})"
    result = save_note_to_joplin(note_title, note_body)
    # Cleanup
    if os.path.exists(photo_path):
        os.remove(photo_path)
    update.message.reply_text(result)

def fetch_note_by_id(note_id):
    url = f'http://localhost:{JOPLIN_PORT}/notes/{note_id}?token={JOPLIN_TOKEN}&fields=id,title,body'  # Include "body" field
    response = requests.get(url)

    if response.status_code == 200:
        note = response.json()
        print(f"Note found: {note.get('title')}, Content length: {len(note.get('body', ''))}")
        return note.get('body')  # Directly return the "body" field
    else:
        print(f"Failed to fetch note. Status code: {response.status_code}, Response: {response.text}")
        return None



def split_messages(message, limit=4096):
    messages = []
    while message:
        if len(message) <= limit:
            messages.append(message)
            break
        else:
            part = message[:limit]
            last_newline = part.rfind('\n')
            if last_newline != -1:
                messages.append(part[:last_newline])
                message = message[last_newline+1:]
            else:
                messages.append(part)
                message = message[limit:]
    return messages

def handle_read(update: Update, context: CallbackContext) -> None:
    if not context.args or len(context.args) != 1:
        update.message.reply_text('Please provide a note ID after the /read command.')
        return
    note_id = context.args[0]
    note_body = fetch_note_by_id(note_id)
    if note_body is None:
        update.message.reply_text('Failed to fetch the note or note not found.')
        return
    parts = split_messages(note_body)
    if not parts:  # Check if splitting resulted in no parts
        update.message.reply_text('Note is empty or too large to process.')
        return
    for part in parts:
        try:
            update.message.reply_text(part)
        except Exception as e:
            print(f"Failed to send message: {e}")  # Log any exceptions
            update.message.reply_text('Error sending part of the note.')


def main():
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(CommandHandler("search", handle_search, pass_args=True))
    dp.add_handler(MessageHandler(Filters.photo, handle_photo))
    dp.add_handler(CommandHandler("read", handle_read, pass_args=True))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
