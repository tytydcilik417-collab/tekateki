import json
import random
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler, ConversationHandler
)

# --- KONFIGURASI ---
ADMIN_ID = 12345678  # GANTI ID KAMU
FILE_SOAL = 'soal.json'
TIMER_DETIK = 15

# States Admin
INPUT_KATEGORI, INPUT_TANYA, INPUT_JAWAB, INPUT_CLUE = range(4)

# --- DATA STORAGE ---
def load_soal():
    try:
        with open(FILE_SOAL, 'r') as f: return json.load(f)
    except: return []

def save_soal(data):
    with open(FILE_SOAL, 'w') as f: json.dump(data, f, indent=4)

DAFTAR_SOAL = load_soal()
scores = {} # {user_id: {"name": str, "points": int}}
game_state = {}

# --- ADMIN FUNCTIONS ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    keyboard = [
        [InlineKeyboardButton("➕ Tambah Soal", callback_data="add_soal")],
        [InlineKeyboardButton("📁 Kirim File Soal (Backup)", callback_data="send_db")]
    ]
    await update.message.reply_text("🛠 **PANEL ADMIN**", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_send_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await context.bot.send_document(chat_id=ADMIN_ID, document=open(FILE_SOAL, 'rb'), 
                                       caption="Ini file soal terbaru. Simpan dan upload ke GitHub!")
    except Exception as e:
        await query.message.reply_text(f"Gagal kirim file: {e}")

# --- GAME FUNCTIONS ---
async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not DAFTAR_SOAL:
        await update.message.reply_text("Database soal kosong!")
        return
    
    # Ambil daftar kategori unik
    kategori_set = list(set([s['kategori'] for s in DAFTAR_SOAL]))
    keyboard = [[InlineKeyboardButton(k, callback_data=f"sel_{k}")] for k in kategori_set]
    
    await update.message.reply_text("📚 **PILIH KATEGORI:**", reply_markup=InlineKeyboardMarkup(keyboard))

async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    kat = query.data.split("_")[1]
    chat_id = update.effective_chat.id
    
    game_state[chat_id] = {"players": set(), "status": "LOBBY", "kategori": kat}
    
    keyboard = [[InlineKeyboardButton("Join Game", callback_data="join_game")]]
    await query.edit_message_text(f"Kategori: **{kat}**\nMinimal 2 orang klik 'Join'!", 
                                  reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if chat_id not in game_state: return
    
    game_state[chat_id]["players"].add(user_id)
    # Update nama di database skor
    scores[user_id] = {"name": update.effective_user.first_name, "points": scores.get(user_id, {}).get("points", 0)}
    
    count = len(game_state[chat_id]["players"])
    await query.answer(f"Kamu Join! ({count}/2)")
    
    if count >= 2 and game_state[chat_id]["status"] == "LOBBY":
        game_state[chat_id]["status"] = "PLAYING"
        await query.message.edit_text("🚀 Pemain cukup! Soal dikirim...")
        await kirim_soal_per_kategori(chat_id, context, game_state[chat_id]["kategori"])

async def kirim_soal_per_kategori(chat_id, context, kat):
    soal_pilihan = [s for s in DAFTAR_SOAL if s['kategori'] == kat]
    soal = random.choice(soal_pilihan)
    
    game_state[chat_id]["jawaban"] = soal['jawaban'].lower()
    game_state[chat_id]["is_answered"] = False
    
    await context.bot.send_message(chat_id, f"❓ **PERTANYAAN**\n\n\"{soal['pertanyaan']}\"\n\n🧩 Clue: `{soal['clue']}`\n⏳ Waktu: {TIMER_DETIK} detik!")
    
    await asyncio.sleep(TIMER_DETIK)
    if not game_state[chat_id].get("is_answered"):
        await context.bot.send_message(chat_id, f"⏰ HABIS! Jawabannya: **{soal['jawaban']}**")
        game_state[chat_id]["is_answered"] = True

async def cek_jawaban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if chat_id not in game_state or game_state[chat_id].get("is_answered"): return
    
    if update.message.text.lower() == game_state[chat_id]["jawaban"]:
        game_state[chat_id]["is_answered"] = True
        scores[user_id]["points"] += 10
        await update.message.reply_text(f"✅ **{update.effective_user.first_name}** BENAR! (+10 Poin)")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not scores:
        await update.message.reply_text("Belum ada skor.")
        return
    # Urutkan Top 3
    top = sorted(scores.items(), key=lambda x: x[1]['points'], reverse=True)[:3]
    text = "🏆 **LEADERBOARD TOP 3** 🏆\n\n"
    for i, (uid, data) in enumerate(top, 1):
        text += f"{i}. {data['name']} — {data['points']} pts\n"
    await update.message.reply_text(text, parse_mode='Markdown')

# --- HANDLERS SETUP ---
# (Gunakan struktur ConversationHandler dari pesan sebelumnya untuk Admin Input)
