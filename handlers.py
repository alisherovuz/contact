import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart

from config import ADMIN_IDS

router = Router()

# Define States
class AppealState(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_direction = State()
    waiting_for_appeal = State()

# List of directions in Latin
DIRECTIONS = [
    "Spin-off", "Startap", "Loyiha topshirish", "Tanlovda ishtirok etish",
    "Yoshlar texnoparklari", "Innovatsion tumanlar", "Tijoratlashtirish loyihalari",
    "Patent olish", "Hamkorlik qilish", "Xorijiy grantlar", "Xorijiy stajirovka",
    "Mustaqil izlanuvchilik", "Oliy ta'limdan keyingi ta'lim", "Boshqa"
]

def get_directions_keyboard():
    # Build inline keyboard for the 14 options (e.g. 2 buttons per row)
    keyboard = []
    row = []
    for i, direction in enumerate(DIRECTIONS, start=1):
        button_text = f"{i}. {direction}"
        callback_data = f"dir_{i-1}"
        row.append(InlineKeyboardButton(text=button_text, callback_data=callback_data))
        if len(row) == 2 or i == len(DIRECTIONS):
            keyboard.append(row)
            row = []
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await message.answer(
        "Innovatsion rivojlanish agentligi direktoriga murojaat yo'llang\n\n"
        "Ism Familiyangiz:"
    )
    await state.set_state(AppealState.waiting_for_name)


@router.message(AppealState.waiting_for_name, F.text)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    
    # Request contact button
    contact_btn = KeyboardButton(text="📞 Raqamni yuborish", request_contact=True)
    keyboard = ReplyKeyboardMarkup(keyboard=[[contact_btn]], resize_keyboard=True, one_time_keyboard=True)
    
    await message.answer("Telefon raqamingiz:", reply_markup=keyboard)
    await state.set_state(AppealState.waiting_for_phone)


@router.message(AppealState.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    if message.contact:
        phone = message.contact.phone_number
    elif message.text:
        phone = message.text
    else:
        await message.answer("Iltimos, telefon raqamingizni matn sifatida kiriting yoki tugmani bosing.")
        return

    await state.update_data(phone=phone)
    
    # Next step: direction with inline keyboard
    # Remove the reply keyboard
    remove_kb = ReplyKeyboardRemove()
    
    await message.answer(
        "Yo'nalishni tanlang:",
        reply_markup=remove_kb
    )
    # Send another message with the inline keyboard
    await message.answer(
        "Ro'yxatdan mos yo'nalishni tanlang:",
        reply_markup=get_directions_keyboard()
    )
    await state.set_state(AppealState.waiting_for_direction)


@router.callback_query(AppealState.waiting_for_direction, F.data.startswith("dir_"))
async def process_direction(callback: CallbackQuery, state: FSMContext):
    direction_idx = int(callback.data.split("_")[1])
    direction_text = DIRECTIONS[direction_idx]
    
    await state.update_data(direction=direction_text)
    
    # Edit the message to show what was selected
    await callback.message.edit_text(f"Tanlangan yo'nalish: {direction_text}")
    
    await callback.message.answer("Murojaatingizni yozma shaklda kiriting:")
    await state.set_state(AppealState.waiting_for_appeal)
    await callback.answer()


@router.message(AppealState.waiting_for_appeal, F.text)
async def process_appeal(message: Message, state: FSMContext):
    data = await state.get_data()
    
    name = data.get("name")
    phone = data.get("phone")
    direction = data.get("direction")
    appeal_text = message.text
    user_id = message.from_user.id
    
    # Construct the message for admin
    admin_msg = (
        f"📝 <b>Yangi murojaat</b>\n\n"
        f"👤 <b>Ism:</b> {name}\n"
        f"📞 <b>Telefon:</b> {phone}\n"
        f"📂 <b>Yo'nalish:</b> {direction}\n"
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
        await message.answer("Murojaatingiz muvaffaqiyatli yuborildi! Tez orada sizga javob beriladi.")
    else:
        await message.answer("Uzr, xatolik yuz berdi va murojaatingiz yuborilmadi. Keyinroq qayta urinib ko'ring.")
    
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
        
        # Admin's reply content
        reply_text = message.text
        if not reply_text:
            reply_text = "Media fayl yoki hujjat qabul qilindi." # Basic fallback if media is sent
            
        notification = f"Agentlikdan javob:\n\n{reply_text}"
        
        try:
            # We can also forward media if the admin sends media instead of text
            if message.photo or message.document or message.video or message.audio or message.voice:
                await message.copy_to(chat_id=user_id)
                # Send the "Answer from agency" prefix text separately if needed, or rely on copy_to
                await message.bot.send_message(chat_id=user_id, text="Agentlikdan yuqoridagi fayl(lar)/javob yuborildi.")
            else:
                await message.bot.send_message(chat_id=user_id, text=notification)
                
            await message.reply("Sizning javobingiz foydalanuvchiga yuborildi!")
        except Exception as e:
            print(f"Failed to send reply to user {user_id}: {e}")
            await message.reply(f"Javob yuborishda xatolik yuz berdi. Foydalanuvchi botni bloklagan bo'lishi mumkin. Xato: {e}")
