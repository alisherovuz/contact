import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart

from config import ADMIN_IDS
from texts import TEXTS

router = Router()

# Define States
class AppealState(StatesGroup):
    waiting_for_language = State()
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_direction = State()
    waiting_for_appeal = State()

def get_directions_keyboard(lang_code):
    directions = TEXTS[lang_code]["directions"]
    keyboard = []
    row = []
    for i, direction in enumerate(directions, start=1):
        row.append(KeyboardButton(text=direction))
        if len(row) == 2 or i == len(directions):
            keyboard.append(row)
            row = []
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    # Ask for language
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data="lang_uz"),
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")
        ]
    ])
    await message.answer("Tilni tanlang / Выберите язык:", reply_markup=keyboard)
    await state.set_state(AppealState.waiting_for_language)

@router.callback_query(AppealState.waiting_for_language, F.data.startswith("lang_"))
async def process_language(callback: CallbackQuery, state: FSMContext):
    lang_code = callback.data.split("_")[1]
    await state.update_data(lang=lang_code)
    
    await callback.message.delete()
    
    t = TEXTS[lang_code]
    await callback.message.answer(t["welcome"])
    await state.set_state(AppealState.waiting_for_name)
    await callback.answer()

@router.message(AppealState.waiting_for_name, F.text)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    
    data = await state.get_data()
    lang_code = data.get("lang", "uz")
    t = TEXTS[lang_code]
    
    # Request contact button
    contact_btn = KeyboardButton(text=t["btn_send_contact"], request_contact=True)
    keyboard = ReplyKeyboardMarkup(keyboard=[[contact_btn]], resize_keyboard=True, one_time_keyboard=True)
    
    await message.answer(t["ask_phone"], reply_markup=keyboard)
    await state.set_state(AppealState.waiting_for_phone)

@router.message(AppealState.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    lang_code = data.get("lang", "uz")
    t = TEXTS[lang_code]

    if message.contact:
        phone = message.contact.phone_number
    elif message.text:
        phone = message.text
    else:
        await message.answer(t["err_phone_format"])
        return

    await state.update_data(phone=phone)
    
    # Next step: direction with reply keyboard
    await message.answer(
        t["ask_direction"],
        reply_markup=get_directions_keyboard(lang_code)
    )
    await state.set_state(AppealState.waiting_for_direction)

@router.message(AppealState.waiting_for_direction, F.text)
async def process_direction(message: Message, state: FSMContext):
    data = await state.get_data()
    lang_code = data.get("lang", "uz")
    t = TEXTS[lang_code]
    directions = t["directions"]
    
    direction_text = message.text
    
    if direction_text not in directions:
        await message.answer(t["err_direction"], reply_markup=get_directions_keyboard(lang_code))
        return
        
    await state.update_data(direction=direction_text)
    
    await message.answer(
        t["ask_appeal"],
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(AppealState.waiting_for_appeal)

@router.message(AppealState.waiting_for_appeal, F.text)
async def process_appeal(message: Message, state: FSMContext):
    data = await state.get_data()
    lang_code = data.get("lang", "uz")
    t = TEXTS[lang_code]
    
    name = data.get("name")
    phone = data.get("phone")
    direction = data.get("direction")
    appeal_text = message.text
    user_id = message.from_user.id
    
    # Construct the message for admin ALWAYS in Uzbek for consistency
    admin_msg = (
        f"📝 <b>Yangi murojaat</b>\n\n"
        f"👤 <b>Ism-familiya:</b> {name}\n"
        f"📞 <b>Telefon:</b> {phone}\n"
        f"📂 <b>Yo'nalish:</b> {direction} ({lang_code.upper()})\n"
        f"🆔 <b>User ID:</b> {user_id}\n\n"
        f"💬 <b>Murojaat:</b>\n{appeal_text}"
    )
    
    success = False
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(chat_id=admin_id, text=admin_msg, parse_mode="HTML")
            success = True
        except Exception as e:
            print(f"Error sending message to admin {admin_id}: {e}")
            
    if success:
        await message.answer(t["success_sent"])
    else:
        await message.answer(t["err_sent"])
    
    await state.clear()

# Admin reply handler (accepts from any of the ADMIN_IDS)
@router.message(F.chat.id.in_(ADMIN_IDS), F.reply_to_message)
async def admin_reply(message: Message):
    original_text = message.reply_to_message.text
    if not original_text:
        return
        
    # Extract User ID from the original message text using regex
    match = re.search(r"User ID:\s*(\d+)", original_text)
    if match:
        user_id = int(match.group(1))
        
        # We don't have user's language stored persistently for the admin reply.
        # But we can try to figure it out from the forwarded direction name, or just use Uzbek as default.
        # It's better to just use a multi-language reply notification or simple uzbek if not stored.
        # Let's send a generic prefix or use the text we sent earlier. We'll use multi-language.
        
        reply_text = message.text
        if not reply_text:
            reply_text = "Media fayl yoki hujjat qabul qilindi. / Получен медиафайл или документ."
            
        notification = f"Agentlikdan javob / Ответ от Агентства:\n\n{reply_text}"
        
        try:
            if message.photo or message.document or message.video or message.audio or message.voice:
                await message.copy_to(chat_id=user_id)
                await message.bot.send_message(chat_id=user_id, text="Agentlikdan yuqoridagi fayl(lar)/javob yuborildi.\nАгентство отправило файл(ы)/ответ выше.")
            else:
                await message.bot.send_message(chat_id=user_id, text=notification)
                
            await message.reply("Sizning javobingiz foydalanuvchiga yuborildi!\nВаш ответ отправлен пользователю!")
        except Exception as e:
            print(f"Failed to send reply to user {user_id}: {e}")
            await message.reply(f"Javob yuborishda xatolik yuz berdi. Foydalanuvchi botni bloklagan bo'lishi mumkin. Xato:\n{e}")
