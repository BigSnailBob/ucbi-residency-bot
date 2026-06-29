import os
import logging
import httpx
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
FORWARD_TO_CHAT_ID = os.getenv("FORWARD_TO_CHAT_ID")
BOOKING_BACKEND_URL = os.getenv("BOOKING_BACKEND_URL", "http://127.0.0.1:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- Conversation states ---
(
    MAIN_MENU,
    NAME,
    PHONE,
    NATIONALITY,
    RESIDENCE,
    TIME_IN_SPAIN,
    INCOME_SOURCE,
    INCOME_SOURCE_OTHER,
    EMPLOYER_LOCATION,
    MONTHLY_INCOME,
    SAVINGS,
    CRIMINAL_RECORD,
    MARITAL_STATUS,
    FAMILY_COUNT,
    EXTRA_NOTES,
    CONFIRM,
    COOP_NAME,
    COOP_CONTACT,
) = range(18)

# --- Keyboards ---
MAIN_MENU_KB = ReplyKeyboardMarkup(
    [
        ["ℹ️ Про наші послуги"],
        ["📅 Записатися на консультацію"],
        ["🤝 Розпочати співпрацю"],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

INCOME_SOURCE_KB = ReplyKeyboardMarkup(
    [
        ["🏢 Іспанське аутономо", "💼 Найманий працівник в Іспанії"],
        ["🇺🇦 Український ФОП", "✏️ Інше"],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

EMPLOYER_KB = ReplyKeyboardMarkup(
    [["🌐 Поза Іспанією", "🇪🇸 В Іспанії"]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

YES_NO_KB = ReplyKeyboardMarkup(
    [["✅ Так", "❌ Ні"]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

MARITAL_KB = ReplyKeyboardMarkup(
    [
        ["💍 Одружений/Одружена", "🧑 Неодружений/Неодружена"],
        ["💔 Розлучений/Розлучена", "🕊️ Вдівець/Вдова"],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

CONFIRM_KB = ReplyKeyboardMarkup(
    [["✅ Підтвердити", "✏️ Заповнити заново"]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

VALID_INCOME_SOURCES = [
    "🏢 Іспанське аутономо",
    "💼 Найманий працівник в Іспанії",
    "🇺🇦 Український ФОП",
    "✏️ Інше",
]
VALID_EMPLOYER = ["🌐 Поза Іспанією", "🇪🇸 В Іспанії"]
VALID_YES_NO = ["✅ Так", "❌ Ні"]
VALID_MARITAL = [
    "💍 Одружений/Одружена",
    "🧑 Неодружений/Неодружена",
    "💔 Розлучений/Розлучена",
    "🕊️ Вдівець/Вдова",
]
VALID_CONFIRM = ["✅ Підтвердити", "✏️ Заповнити заново"]

ABOUT_SERVICES_TEXT = """🏛️ *Послуги UCBI: Модифікація тимчасового захисту*

Ми допомагаємо громадянам України перейти з тимчасового захисту на посвідку на проживання в Іспанії 🇪🇸

До кожного пакету входить:
• Інформаційний супровід щодо переліку документів та умов
• Заповнення всіх необхідних форм
• Підготовка пакету документів згідно з чинними вимогами
• Подання заявки
• Відслідковування стану заявки та реагування на дозапити

💼 *Модифікація на резиденцію на підставі робочого контракту* — 350 €
🏢 *Модифікація для зареєстрованих як Autónomo* — 350 €
👶 *Модифікація для дітей на тимчасовому захисті* — 150 €

_Ціни вказані без ПДВ 21%. Обов'язкові державні мита та збори оплачуються окремо._

💬 *Персональна консультація щодо вашої ситуації* — 45 €
Запишіться через бота, щоб отримати відповідь на всі ваші запитання від нашого спеціаліста.

📧 info@ucbi.es"""


async def invalid_button(update: Update, keyboard) -> None:
    await update.message.reply_text(
        "👆 Будь ласка, оберіть один із варіантів нижче:",
        reply_markup=keyboard,
    )


def build_summary(data: dict) -> str:
    return (
        f"📋 Нова заявка — Резиденція\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Ім'я: {data.get('name', '—')}\n"
        f"📞 Контакт: {data.get('phone', '—')}\n"
        f"🌍 Громадянство: {data.get('nationality', '—')}\n"
        f"🏠 Країна проживання: {data.get('residence', '—')}\n"
        f"⏳ Час перебування на захисті в Іспанії: {data.get('time_in_spain', '—')}\n"
        f"💼 Джерело доходу: {data.get('income_source', '—')}\n"
        f"🌐 Роботодавець/клієнти: {data.get('employer_location', '—')}\n"
        f"💶 Місячний дохід: {data.get('monthly_income', '—')} €\n"
        f"💰 Заощадження: {data.get('savings', '—')}\n"
        f"⚖️ Судимості: {data.get('criminal_record', '—')}\n"
        f"👫 Сімейний стан: {data.get('marital_status', '—')}\n"
        f"👨‍👩‍👧 Члени родини до заявки: {data.get('family_count', '—')}\n"
        f"💬 Додаткові коментарі: {data.get('extra_notes', '—')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )


# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "👋 Привіт!\n\n"
        "Ласкаво просимо до сервісу переходу з тимчасового захисту на резиденцію в Іспанії 🇪🇸\n\n"
        "Оберіть, що вас цікавить:",
        reply_markup=MAIN_MENU_KB,
    )
    return MAIN_MENU


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == "ℹ️ Про наші послуги":
        await update.message.reply_text(
            ABOUT_SERVICES_TEXT,
            parse_mode="Markdown",
            reply_markup=MAIN_MENU_KB,
        )
        return MAIN_MENU

    elif text == "📅 Записатися на консультацію":
        await update.message.reply_text(
            "Чудово! Для запису на консультацію нам потрібно заповнити коротку анкету.\n\n"
            "Як вас звати? (ім'я та прізвище)",
            reply_markup=ReplyKeyboardRemove(),
        )
        return NAME

    elif text == "🤝 Розпочати співпрацю":
        await update.message.reply_text(
            "🤝 Чудово! Давайте познайомимося.\n\n"
            "Як вас звати? (ім'я та прізвище)",
            reply_markup=ReplyKeyboardRemove(),
        )
        return COOP_NAME

    else:
        await update.message.reply_text(
            "👆 Будь ласка, оберіть один із варіантів нижче:",
            reply_markup=MAIN_MENU_KB,
        )
        return MAIN_MENU


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text(
        "📞 Вкажіть ваш контактний номер телефону або Telegram username\n"
        "(наприклад: +380XXXXXXXXX або @username)",
    )
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["phone"] = update.message.text.strip()
    await update.message.reply_text("🌍 Яке у вас громадянство?")
    return NATIONALITY


async def get_nationality(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["nationality"] = update.message.text.strip()
    await update.message.reply_text("🏠 У якій країні ви зараз проживаєте?")
    return RESIDENCE


async def get_residence(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["residence"] = update.message.text.strip()
    await update.message.reply_text(
        "⏳ Скільки часу ви перебуваєте під тимчасовим захистом в Іспанії?\n"
        "(наприклад: 6 місяців, 1 рік, 2 роки тощо)",
    )
    return TIME_IN_SPAIN


async def get_time_in_spain(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["time_in_spain"] = update.message.text.strip()
    await update.message.reply_text(
        "💼 Яке ваше джерело доходу?",
        reply_markup=INCOME_SOURCE_KB,
    )
    return INCOME_SOURCE


async def get_income_source(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text not in VALID_INCOME_SOURCES:
        await invalid_button(update, INCOME_SOURCE_KB)
        return INCOME_SOURCE

    if text == "✏️ Інше":
        context.user_data["income_source_raw"] = text
        await update.message.reply_text(
            "✏️ Будь ласка, вкажіть ваше джерело доходу:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return INCOME_SOURCE_OTHER

    context.user_data["income_source"] = text
    await update.message.reply_text(
        "🌐 Ваш роботодавець або клієнти знаходяться:",
        reply_markup=EMPLOYER_KB,
    )
    return EMPLOYER_LOCATION


async def get_income_source_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["income_source"] = f"Інше: {update.message.text.strip()}"
    await update.message.reply_text(
        "🌐 Ваш роботодавець або клієнти знаходяться:",
        reply_markup=EMPLOYER_KB,
    )
    return EMPLOYER_LOCATION


async def get_employer_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text.strip() not in VALID_EMPLOYER:
        await invalid_button(update, EMPLOYER_KB)
        return EMPLOYER_LOCATION
    context.user_data["employer_location"] = update.message.text.strip()
    await update.message.reply_text(
        "💶 Який ваш середній місячний дохід у євро?\n"
        "(введіть лише число, наприклад: 1500)",
        reply_markup=ReplyKeyboardRemove(),
    )
    return MONTHLY_INCOME


async def get_monthly_income(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["monthly_income"] = update.message.text.strip()
    await update.message.reply_text(
        "💰 Чи маєте ви заощадження на банківському рахунку?\n"
        "(якщо так — вкажіть приблизну суму, якщо ні — напишіть «Ні»)",
    )
    return SAVINGS


async def get_savings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["savings"] = update.message.text.strip()
    await update.message.reply_text(
        "⚖️ Чи є у вас судимості в Україні або будь-якій іншій країні за останні 5 років?",
        reply_markup=YES_NO_KB,
    )
    return CRIMINAL_RECORD


async def get_criminal_record(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text.strip() not in VALID_YES_NO:
        await invalid_button(update, YES_NO_KB)
        return CRIMINAL_RECORD
    context.user_data["criminal_record"] = update.message.text.strip()
    await update.message.reply_text(
        "👫 Який ваш сімейний стан?",
        reply_markup=MARITAL_KB,
    )
    return MARITAL_STATUS


async def get_marital_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text.strip() not in VALID_MARITAL:
        await invalid_button(update, MARITAL_KB)
        return MARITAL_STATUS
    context.user_data["marital_status"] = update.message.text.strip()
    await update.message.reply_text(
        "👨‍👩‍👧 Чи будете ви включати членів родини до заявки на резиденцію?\n"
        "(якщо так — вкажіть кількість, якщо ні — напишіть «0»)",
        reply_markup=ReplyKeyboardRemove(),
    )
    return FAMILY_COUNT


async def get_family_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["family_count"] = update.message.text.strip()
    await update.message.reply_text(
        "💬 Останнє питання: чи є у вас додаткові запитання або коментарі для нашого спеціаліста?\n"
        "(або напишіть «Немає»)",
    )
    return EXTRA_NOTES


async def get_extra_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["extra_notes"] = update.message.text.strip()
    summary = build_summary(context.user_data)
    await update.message.reply_text(
        f"✅ Дякуємо! Ось ваші відповіді:\n\n{summary}\n\n"
        "Все правильно? Натисніть «Підтвердити», щоб перейти до вибору часу консультації.\n"
        "Або «Заповнити заново», щоб почати з початку.",
        reply_markup=CONFIRM_KB,
    )
    return CONFIRM


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text not in VALID_CONFIRM:
        await invalid_button(update, CONFIRM_KB)
        return CONFIRM

    if "заново" in text.lower():
        context.user_data.clear()
        await update.message.reply_text(
            "🔄 Починаємо заново! Як вас звати?",
            reply_markup=ReplyKeyboardRemove(),
        )
        return NAME

    user = update.effective_user
    tg_info = f"@{user.username}" if user.username else f"ID: {user.id}"
    summary = build_summary(context.user_data)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BOOKING_BACKEND_URL}/session",
                json={
                    "telegram_id": user.id,
                    "name": context.user_data.get("name"),
                    "summary": f"{summary}\n\nTelegram: {tg_info}",
                }
            )
            data = resp.json()
            session_id = data["session_id"]

        booking_url = f"{FRONTEND_URL}/book/{session_id}"

        await update.message.reply_text(
            "🎉 Дякуємо! Останній крок — оберіть зручний час для консультації (до 30 хвилин, вартість 45€):\n\n"
            f"👉 {booking_url}",
            reply_markup=ReplyKeyboardRemove(),
        )
    except Exception as e:
        logger.error(f"Failed to create booking session: {e}")
        await update.message.reply_text(
            "⚠️ Виникла технічна помилка. "
            "Будь ласка, спробуйте ще раз або зв'яжіться з нами напряму.",
            reply_markup=ReplyKeyboardRemove(),
        )

    return ConversationHandler.END


async def coop_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["coop_name"] = update.message.text.strip()
    await update.message.reply_text(
        "📞 Вкажіть ваш контактний номер телефону або Telegram username\n"
        "(наприклад: +380XXXXXXXXX або @username)",
    )
    return COOP_CONTACT


async def coop_get_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["coop_contact"] = update.message.text.strip()
    user = update.effective_user
    tg_info = f"@{user.username}" if user.username else f"ID: {user.id}"
    coop_name = context.user_data.get("coop_name")
    coop_contact = context.user_data.get("coop_contact")

    try:
        await context.bot.send_message(
            chat_id=int(FORWARD_TO_CHAT_ID),
            text=(
                f"🤝 Новий запит на співпрацю\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 Ім'я: {coop_name}\n"
                f"📞 Контакт: {coop_contact}\n"
                f"💬 Telegram: {tg_info}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
            ),
        )
        logger.info(f"Cooperation request forwarded to {FORWARD_TO_CHAT_ID}")
    except Exception as e:
        logger.error(f"Failed to forward cooperation request to {FORWARD_TO_CHAT_ID}: {e}")

    await update.message.reply_text(
        f"🎉 Дякуємо, {coop_name}!\n\n"
        "Ваш запит отримано. Наш спеціаліст зв'яжеться з вами найближчим часом через Telegram або за вказаним контактом.\n\n"
        "До зустрічі! 🇪🇸",
        reply_markup=MAIN_MENU_KB,
    )
    return MAIN_MENU


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Розмову завершено. Якщо захочете повернутися — просто напишіть /start",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            NATIONALITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_nationality)],
            RESIDENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_residence)],
            TIME_IN_SPAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time_in_spain)],
            INCOME_SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_income_source)],
            INCOME_SOURCE_OTHER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_income_source_other)],
            EMPLOYER_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_employer_location)],
            MONTHLY_INCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_monthly_income)],
            SAVINGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_savings)],
            CRIMINAL_RECORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_criminal_record)],
            MARITAL_STATUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_marital_status)],
            FAMILY_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_family_count)],
            EXTRA_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_extra_notes)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)],
            COOP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, coop_get_name)],
            COOP_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, coop_get_contact)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)
    logger.info("Residency bot started. Polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
