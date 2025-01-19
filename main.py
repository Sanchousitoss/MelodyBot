import os
import json
import logging
from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from yt_dlp import YoutubeDL

def default_converter(o):
    if isinstance(o, date):
        return o.isoformat()
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

# Налаштування логування
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Ініціалізація змінних
user_data = {}
unlimited_users = set()
TOKEN = "7708428765:AAF7NyREIWq-zhOVkc6aiaHx4jYqg8pKgxM"
DOWNLOAD_FOLDER = './downloads/'
ADMIN_USER_ID = 5857286638
CHANNEL_NICK = "@melodytrack_bot"
SUBSCRIPTION_PRICES = {
    'en': "15 UAH",
    'ru': "15 UAH",
    'uk': "15 UAH"
}
button_texts = {
    "uk": {
        "help": "Допомога (FAQ) ❓",
        "benefits": "Переваги 💡",
        "buy_subscription": "Купити безлімітний доступ 💳",
        "view_downloads": "Переглянути завантажені треки 🎶",
        "change_language": "Змінити мову 🌐",
        "back": "Назад 🔙"
    },
    "ru": {
        "help": "Помощь (FAQ) ❓",
        "benefits": "Преимущества 💡",
        "buy_subscription": "Купить безлимитный доступ 💳",
        "view_downloads": "Просмотреть загруженные треки 🎶",
        "change_language": "Изменить язык 🌐",
        "back": "Назад 🔙"
    },
    "en": {
        "help": "Help (FAQ) ❓",
        "benefits": "Benefits 💡",
        "buy_subscription": "Buy Unlimited Access 💳",
        "view_downloads": "View Downloaded Tracks 🎶",
        "change_language": "Change Language 🌐",
        "back": "Back 🔙"
    }
}

greeting_messages = {
    "uk": "Привіт! 👋 Я бот, який допоможе вам завантажити аудіо з YouTube. Надішліть мені посилання на відео, і я перетворю його в MP3 файл. 🎵",
    "ru": "Привет! 👋 Я бот, который поможет вам скачать аудио с YouTube. Отправьте мне ссылку на видео, и я преобразую его в MP3 файл. 🎵",
    "en": "Hello! 👋 I'm a bot that will help you download audio from YouTube. Send me a link to a video, and I'll convert it to an MP3 file. 🎵"
}

# Завантаження даних з файлу JSON
def load_user_data(user_data_file=None):
    global user_data
    if os.path.exists('user_data.json'):
        try:
            with open('user_data.json', 'r') as f:
                user_data = json.load(f)
            logging.info("Дані успішно завантажені з user_data.json")
        except json.JSONDecodeError as e:
            logging.error(f"Помилка декодування JSON: {e}. Ініціалізую порожні дані.")
            logging.error("Вміст файлу user_data.json:")
            with open('user_data.json', 'r') as f:
                logging.error(f.read())
            user_data = {}
            save_user_data()  # Створити файл з порожніми даними
    else:
        logging.info("Файл user_data.json не знайдено. Ініціалізую порожні дані.")
        user_data = {}
        save_user_data()  # Створити файл з порожніми даними

# Збереження даних у файл JSON
def save_user_data():
    with open('user_data.json', 'w') as f:
        json.dump(user_data, f, indent=4, default=default_converter)
    logging.info("Дані збережено в user_data.json")

# Завантаження даних при старті програми
load_user_data()

# Команда для додавання користувача до списку з безлімітним доступом
async def add_unlimited_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    if chat_id != ADMIN_USER_ID:
        await update.message.reply_text("У вас немає прав для використання цієї команди.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Використання: /add_unlimited_user <user_id>")
        return

    user_id = int(context.args[0])
    unlimited_users.add(user_id)
    save_user_data()
    await update.message.reply_text(f"Користувача {user_id} додано до списку з безлімітним доступом.")

# Функція для показу меню
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, welcome_message: bool) -> None:
    chat_id = update.message.chat_id if update.message else update.callback_query.message.chat_id
    if chat_id not in user_data:
        user_data[chat_id] = {'downloads_today': 0, 'last_download': datetime.today().date(), 'downloads': [], 'language': 'en'}
    language = user_data[chat_id]['language']

    keyboard = [
        [InlineKeyboardButton(button_texts[language]["help"], callback_data="help")],
        [InlineKeyboardButton(button_texts[language]["benefits"], callback_data="benefits")],
        [InlineKeyboardButton(button_texts[language]["buy_subscription"], callback_data="buy_subscription")],
        [InlineKeyboardButton(button_texts[language]["view_downloads"], callback_data="view_downloads")],
        [InlineKeyboardButton(button_texts[language]["change_language"], callback_data="change_language")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = greeting_messages[language] if welcome_message else button_texts[language]["change_language"]

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup)

# Функція для конвертації YouTube відео в MP3
async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id if update.message else update.callback_query.message.chat_id

    if chat_id not in user_data:
        user_data[chat_id] = {'downloads_today': 0, 'last_download': datetime.today().date(), 'downloads': [], 'language': 'en'}

    language = user_data[chat_id]['language']

    messages = {
        "uk": {
            "downloading": "Завантаження триває... ⏳",
            "limit_reached": "Ви досягли свого щоденного ліміту в 5 завантажень. Поверніться завтра або придбайте безлімітний доступ. 🎉",
            "subscribe_prompt": f"Для використання бота, будь ласка, підпишіться на наш канал {CHANNEL_NICK}. 🤝",
            "download_success": "Завантаження успішне! У вас залишилось {remaining_downloads} завантажень на сьогодні. 🎉",
            "download_success_no_remaining": "Завантаження успішне! У вас закінчились всі безкоштовні завантаження на сьогодні. 🎉",
            "download_error": "Помилка обробки посилання. Спробуйте ще раз. 😔",
            "invalid_link": "Будь ласка, надайте дійсне посилання на YouTube. 📹"
        },
        "ru": {
            "downloading": "Загрузка продолжается... ⏳",
            "limit_reached": "Вы достигли своего дневного лимита в 5 загрузок. Вернитесь завтра или купите безлимитный доступ. 🎉",
            "subscribe_prompt": f"Для использования бота, пожалуйста, подпишитесь на наш канал {CHANNEL_NICK}. 🤝",
            "download_success": "Загрузка успешна! У вас осталось {remaining_downloads} загрузок на сегодня. 🎉",
            "download_success_no_remaining": "Загрузка успешна! У вас закончились все бесплатные загрузки на сегодня. 🎉",
            "download_error": "Ошибка обработки ссылки. Попробуйте еще раз. 😔",
            "invalid_link": "Пожалуйста, предоставьте действующую ссылку на YouTube. 📹"
        },
        "en": {
            "downloading": "Downloading in progress... ⏳",
            "limit_reached": "You have reached your daily limit of 5 downloads. Come back tomorrow or purchase unlimited access. 🎉",
            "subscribe_prompt": f"To use the bot, please subscribe to our channel {CHANNEL_NICK}. 🤝",
            "download_success": "Download successful! You have {remaining_downloads} downloads left for today. 🎉",
            "download_success_no_remaining": "Download successful! You have used up all your free downloads for today. 🎉",
            "download_error": "Error processing the link. Please try again. 😔",
            "invalid_link": "Please provide a valid link to YouTube. 📹"
        }
    }

    # Перевірка ліміту завантажень
    today = datetime.today().date()
    if user_data[chat_id]['last_download'] != today:
        user_data[chat_id]['downloads_today'] = 0
        user_data[chat_id]['last_download'] = today

    if chat_id not in unlimited_users:
        limit_reached = user_data[chat_id]['downloads_today'] >= 5
    else:
        limit_reached = False

    # Перевірка на наявність посилання на YouTube
    if update.message and any(domain in update.message.text for domain in ['youtube.com', 'youtu.be']):
        video_url = update.message.text

        if limit_reached:
            await update.message.reply_text(
                messages[language]["limit_reached"],
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(button_texts[language]["buy_subscription"], callback_data="buy_subscription")]
                ]))
            return

        # Перевірка підписки на канал
        user_status = await context.bot.get_chat_member(CHANNEL_NICK, chat_id)
        if user_status['status'] == 'left':
            await update.message.reply_text(
                messages[language]["subscribe_prompt"],
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Підписатися", url=f"https://t.me/{CHANNEL_NICK[1:]}", callback_data="check_subscription")]
                ]))
            return

        await update.message.reply_text(messages[language]["downloading"])

        # Завантаження аудіо
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
            }

            with YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(video_url, download=True)
                # Очистка назви файлу від спеціальних символів
                safe_title = "".join(char if char.isalnum() else "_" for char in info_dict['title'])
                mp3_file_path = os.path.join(DOWNLOAD_FOLDER, f"{safe_title}.mp3")

            track_name = info_dict['title']
            if track_name not in user_data[chat_id]['downloads']:
                user_data[chat_id]['downloads'].append(mp3_file_path)

            await context.bot.send_audio(chat_id=chat_id, audio=open(mp3_file_path, 'rb'))

            user_data[chat_id]['downloads_today'] += 1
            remaining_downloads = 5 - user_data[chat_id]['downloads_today']
            if remaining_downloads > 0:
                await update.message.reply_text(messages[language]["download_success"].format(remaining_downloads=remaining_downloads))
            else:
                await update.message.reply_text(messages[language]["download_success_no_remaining"])

            # Збереження даних після завантаження
            save_user_data()

        except Exception as e:
            logging.error(f"Помилка обробки посилання: {e}")
            await update.message.reply_text(messages[language]["download_error"])
    else:
        await update.message.reply_text(messages[language]["invalid_link"])

# Функція для купівлі підписки
async def buy_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.callback_query.message.chat_id
    language = user_data[chat_id]['language']

    messages = {
        "uk": "Щоб отримати безлімітний доступ, будь ласка, надішліть {price} на наступний рахунок:\n\n"
              "Monobank: 5375411591445601\n\n"
              "Під час переказу в коментарях вкажіть: 'Підписка на MelodyBot' 🎶\n\n"
              "Після оплати надішліть скріншот платежу @sanajros для перевірки. 💳",
        "ru": "Чтобы получить безлимитный доступ, пожалуйста, отправьте {price} на следующий счет:\n\n"
              "Monobank: 5375411591445601\n\n"
              "При переводе укажите в комментариях: 'Подписка на MelodyBot' 🎶\n\n"
              "После оплаты отправьте скриншот платежа @sanajros для проверки. 💳",
        "en": "To get unlimited access, please send {price} to the following account:\n\n"
              "Monobank: 5375411591445601\n\n"
              "When transferring, indicate in the comments: 'Subscription to MelodyBot' 🎶\n\n"
              "After payment, send a screenshot of the payment to @sanajros for verification. 💳"
    }

    price = SUBSCRIPTION_PRICES[language]
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        messages[language].format(price=price),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(button_texts[language]["back"], callback_data="go_back")]
        ]))

# Функція для перегляду завантажених треків
async def view_downloads(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id if update.message else update.callback_query.message.chat_id
    if chat_id not in user_data:
        user_data[chat_id] = {'downloads_today': 0, 'last_download': datetime.today().date(), 'downloads': [], 'language': 'en'}
    language = user_data[chat_id]['language']

    messages = {
        "uk": "Ви ще не завантажили жодного трека. 🎵",
        "ru": "Вы еще не загрузили ни одного трека. 🎵",
        "en": "You haven't downloaded any tracks yet. 🎵",
        "downloaded_tracks": {
            "uk": "Ваші завантажені треки:",
            "ru": "Ваши загруженные треки:",
            "en": "Your downloaded tracks:",
            "completed": {
                "uk": "Перегляд завантажених треків завершено.",
                "ru": "Просмотр загруженных треков завершен.",
                "en": "Viewing of downloaded tracks is completed."
            }
        }
    }

    async def send_message(text, reply_markup=None):
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.callback_query.message.reply_text(text, reply_markup=reply_markup)

    if chat_id not in user_data or not user_data[chat_id]['downloads']:
        await send_message(messages[language])
    else:
        await send_message(messages['downloaded_tracks'][language])

        for file_path in user_data[chat_id]['downloads']:
            with open(file_path, 'rb') as audio_file:
                await context.bot.send_audio(chat_id=chat_id, audio=audio_file)

        await send_message(messages['downloaded_tracks']['completed'][language],
                           reply_markup=InlineKeyboardMarkup([
                               [InlineKeyboardButton(button_texts[language]["back"], callback_data="go_back")]
                           ]))

# Стартова команда
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id if update.message else update.callback_query.message.chat_id

    if chat_id not in user_data:
        user_data[chat_id] = {'downloads_today': 0, 'last_download': datetime.today().date(), 'downloads': [], 'language': None}

    if user_data[chat_id]['language'] is None:
        keyboard = [
            [InlineKeyboardButton("Українська 🇺🇦", callback_data="set_language_uk")],
            [InlineKeyboardButton("English 🇬🇧", callback_data="set_language_en")],
            [InlineKeyboardButton("Русский 🇷🇺", callback_data="set_language_ru")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Ласкаво просимо! Оберіть мову для продовження: 🌍",
            reply_markup=reply_markup
        )
    else:
        await show_menu(update, context, welcome_message=False)

# Функція для обробки кнопок меню
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id

    # Ініціалізація користувача, якщо ще не ініціалізовано
    if chat_id not in user_data:
        user_data[chat_id] = {'downloads_today': 0, 'last_download': datetime.today().date(), 'downloads': [], 'language': 'en'}

    await query.answer()

    language = user_data[chat_id]['language']

    if query.data == "help":
        messages = {
            "uk": "FAQ:\n\n1. Надішліть посилання на YouTube для завантаження MP3. 🎥\n2. Ви можете завантажити до 5 треків на день безкоштовно. 🆓\n3. Щоб зняти обмеження, придбайте безлімітний доступ. 🔓\n4. Зв'язок з підтримкою: @sanajros 📞",
            "ru": "FAQ:\n\n1. Отправьте ссылку на YouTube для загрузки MP3. 🎥\n2. Вы можете загрузить до 5 треков в день бесплатно. 🆓\n3. Чтобы снять ограничения, купите безлимитный доступ. 🔓\n4. Связаться с поддержкой: @sanajros 📞",
            "en": "FAQ:\n\n1. Send a link to YouTube to download MP3. 🎥\n2. You can download up to 5 tracks per day for free. 🆓\n3. To remove limits, purchase unlimited access. 🔓\n4. Contact support: @sanajros 📞"
        }
        await query.message.edit_text(messages[language], reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(button_texts[language]["back"], callback_data="go_back")]
        ]))

    elif query.data == "benefits":
        messages = {
            "uk": "Переваги:\n\nБез безлімітної версії:\n- До 5 завантажень на день\n- Висока якість MP3 файлів\n\nЗ безлімітною версією:\n- Безлімітні завантаження\n- Пріоритетна підтримка\n- Висока якість MP3 файлів",
            "ru": "Преимущества:\n\nБез безлимитной версии:\n- До 5 загрузок в день\n- Высокое качество MP3 файлов\n\nС безлимитной версией:\n- Безлимитные загрузки\n- Приоритетная поддержка\n- Высокое качество MP3 файлов",
            "en": "Benefits:\n\nWithout Unlimited Version:\n- Up to 5 downloads per day\n- High quality MP3 files\n\nWith Unlimited Version:\n- Unlimited downloads\n- Priority support\n- High quality MP3 files"
        }
        await query.message.edit_text(messages[language], reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(button_texts[language]["back"], callback_data="go_back")]
        ]))

    elif query.data == "check_subscription":
        user_status = await context.bot.get_chat_member(CHANNEL_NICK, chat_id)
        if user_status['status'] == 'left':
            messages = {
                "uk": f"Для використання бота, будь ласка, підпишіться на наш канал {CHANNEL_NICK}. 🤝",
                "ru": f"Для использования бота, пожалуйста, подпишитесь на наш канал {CHANNEL_NICK}. 🤝",
                "en": f"To use the bot, please subscribe to our channel {CHANNEL_NICK}. 🤝"
            }
            await query.message.edit_text(messages[language],
                                          reply_markup=InlineKeyboardMarkup([
                                              [InlineKeyboardButton("Підписатися",
                                                                    url=f"https://t.me/{CHANNEL_NICK[1:]}",
                                                                    callback_data="check_subscription")]
                                          ]))
        else:
            messages = {
                "uk": "Дякуємо за підписку! Тепер ви можете користуватися ботом. 🎉",
                "ru": "Спасибо за подписку! Теперь вы можете использовать бота. 🎉",
                "en": "Thank you for subscribing! You can now use the bot. 🎉"
            }
            await query.message.edit_text(messages[language], reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(button_texts[language]["back"], callback_data="go_back")]
            ]))

    elif query.data == "change_language":
        keyboard = [
            [InlineKeyboardButton("Українська 🇺🇦", callback_data="set_language_uk")],
            [InlineKeyboardButton("English 🇬🇧", callback_data="set_language_en")],
            [InlineKeyboardButton("Русский 🇷🇺", callback_data="set_language_ru")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            "Оберіть мову для продовження: 🌍",
            reply_markup=reply_markup
        )

    elif query.data.startswith("set_language_"):
        language_code = query.data.split("_")[-1]
        user_data[chat_id]['language'] = language_code
        await show_menu(update, context, welcome_message=True)

    elif query.data == "go_back":
        await show_menu(update, context, welcome_message=False)

# Основна функція
def main() -> None:
    # Завантаження даних при старті бота
    load_user_data()

    application = Application.builder().token(TOKEN).build()

    # Видалення вебхука перед запуском бота
    application.bot.delete_webhook()

    # Реєстрація обробників команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add_unlimited_user", add_unlimited_user))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_audio))
    application.add_handler(CallbackQueryHandler(menu_handler,
                                                 pattern="^(help|benefits|check_subscription|set_language_en|set_language_ru|set_language_uk|change_language|go_back)$"))
    application.add_handler(CallbackQueryHandler(buy_subscription, pattern="buy_subscription"))
    application.add_handler(CallbackQueryHandler(view_downloads, pattern="view_downloads"))

    # Запуск бота
    logging.info("Запуск бота...")
    application.run_polling()

if __name__ == '__main__':
    main()