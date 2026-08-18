import discord
from discord.ext import commands
import random
import sqlite3

# =========================================================
# KHỞI TẠO BOT & INTENTS
# =========================================================
intents = discord.Intents.default()
intents.message_content = True  # Bắt buộc bật Message Content Intent trên Discord Developer Portal

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================================================
# KHỞI TẠO VÀ CẤU HÌNH DATABASE
# =========================================================
conn = sqlite3.connect("noitu.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS players (
    user_id TEXT PRIMARY KEY,
    name TEXT,
    xp INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0
)
""")
conn.commit()

# Nạp danh sách từ nối từ file noitu_words.txt
with open("noitu_words.txt", "r", encoding="utf-8") as f:
    WORDS = set(line.strip().lower() for line in f if line.strip())

# Quản lý trận đấu theo Channel ID
games = {}

def get_level(xp):
    return (xp // 100) + 1

def add_xp(user, amount):
    user_id = str(user.id)
    name = user.display_name
    cursor.execute("SELECT xp FROM players WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        new_xp = row[0] + amount
        cursor.execute("UPDATE players SET xp = ?, name = ? WHERE user_id = ?", (new_xp, name, user_id))
    else:
        cursor.execute("INSERT INTO players (user_id, name, xp, wins) VALUES (?, ?, ?, 0)", (user_id, name, amount))
    conn.commit()

# =========================================================
# SỰ KIỆN KHỞI CHẠY (ON_READY)
# =========================================================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot {bot.user} đã sẵn sàng hoạt động!")

# =========================================================
# LỆNH BẮT ĐẦU GAME (/NOITU)
# =========================================================
@bot.tree.command(name="noitu", description="Bắt đầu phòng nối từ nhiều người chơi (vô thời hạn)")
async def start_noitu(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    
    if channel_id in games:
        await interaction.response.send_message("⚠️ Trong kênh này đang có trận đấu nối từ diễn ra!", ephemeral=True)
        return

    # Chọn ngẫu nhiên 1 từ 2 tiếng để khởi tạo
    valid_starts = [w for w in WORDS if len(w.split()) == 2]
    if not valid_starts:
        await interaction.response.send_message("❌ Từ điển không có cụm 2 từ hợp lệ!", ephemeral=True)
        return

    start_word = random.choice(valid_starts)

    games[channel_id] = {
        'last_word': start_word,
        'last_user_id': None,
        'used_words': {start_word}
    }

    embed = discord.Embed(
        title="🎮 PHÒNG NỐI TỪ MULTIPLAYER BẮT ĐẦU!",
        description=(
            f"Từ khởi đầu: **{start_word.upper()}**\n\n"
            f"👉 Mọi người hãy nhập cụm **2 từ** bắt đầu bằng: **{start_word.split()[-1].upper()}**\n"
            "♾️ Trận đấu **không giới hạn thời gian**.\n"
            "🚫 Bạn không được tự nối từ của chính mình liên tiếp!\n"
            "🛑 Dùng lệnh `/stop` để kết thúc phòng chơi bất kỳ lúc nào."
        ),
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

# =========================================================
# LỆNH HỦY GAME (/STOP)
# =========================================================
@bot.tree.command(name="stop", description="Kết thúc trận đấu nối từ")
async def stop_noitu(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    if channel_id in games:
        del games[channel_id]
        await interaction.response.send_message("🛑 Đã kết thúc trận đấu nối từ!")
    else:
        await interaction.response.send_message("Hiện không có trận đấu nào trong kênh này.", ephemeral=True)

# =========================================================
# XỬ LÝ TIN NHẮN NỐI TỪ (ON_MESSAGE)
# =========================================================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    channel_id = message.channel.id

    if channel_id in games:
        game = games[channel_id]
        user_input = message.content.strip().lower()
        input_parts = user_input.split()

        # Chỉ xử lý khi người chơi gõ đúng 2 từ
        if len(input_parts) == 2:
            last_word_parts = game['last_word'].split()
            required_first_word = last_word_parts[-1]

            # 1. Kiểm tra nếu cùng 1 người tự nối tiếp
            if str(message.author.id) == game['last_user_id']:
                await message.add_reaction("❌")
                await message.channel.send(f"⚠️ {message.author.mention}, bạn phải đợi người chơi khác nối từ trước!", delete_after=4)
                return

            # 2. Kiểm tra từ đầu tiên có khớp với tiếng cuối của từ trước không
            if input_parts[0] != required_first_word:
                return

            # 3. Kiểm tra từ có trong từ điển không
            if user_input not in WORDS:
                await message.add_reaction("❓")
                await message.channel.send(f"❌ Từ **{user_input}** không có trong từ điển!", delete_after=4)
                return

            # 4. Kiểm tra từ đã dùng trong trận chưa
            if user_input in game['used_words']:
                await message.add_reaction("⚠️")
                await message.channel.send(f"⚠️ Từ **{user_input}** đã được dùng rồi!", delete_after=4)
                return

            # --- NỐI TỪ THÀNH CÔNG ---
            game['used_words'].add(user_input)
            game['last_word'] = user_input
            game['last_user_id'] = str(message.author.id)

            # Cộng XP cho câu trả lời hợp lệ
            add_xp(message.author, 10)
            await message.add_reaction("✅")

    await bot.process_commands(message)

# =========================================================
# BẢNG XẾP HẠNG (/TOP)
# =========================================================
@bot.tree.command(name="top", description="Xem bảng xếp hạng nối từ")
async def top(interaction: discord.Interaction):
    cursor.execute("""
        SELECT user_id, name, xp, wins
        FROM players
        ORDER BY xp DESC
        LIMIT 10
    """)
    players = cursor.fetchall()

    if not players:
        await interaction.response.send_message("📊 Chưa có dữ liệu.")
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    top_1_avatar_url = None

    for i, player in enumerate(players):
        user_id_str, name, xp, wins = player
        medal = medals[i] if i < 3 else f"**{i + 1}.**"
        level = get_level(xp)

        lines.append(f"{medal} <@{user_id_str}> — Level {level} — **{xp} XP** — **{wins} 🏆**")

        if i == 0:
            try:
                top_1_user = await bot.fetch_user(int(user_id_str))
                if top_1_user and top_1_user.avatar:
                    top_1_avatar_url = top_1_user.avatar.url
                elif top_1_user:
                    top_1_avatar_url = top_1_user.default_avatar.url
            except Exception:
                top_1_avatar_url = None

    embed = discord.Embed(
        title="🏆 BẢNG XẾP HẠNG NỐI TỪ",
        description="\n".join(lines),
        color=discord.Color.gold()
    )

    if top_1_avatar_url:
        embed.set_thumbnail(url=top_1_avatar_url)

    await interaction.response.send_message(embed=embed)

# =========================================================
# CHẠY BOT (Thay TOKEN của bạn vào đây)
# =========================================================
import os
bot.run(os.getenv("BOT_TOKEN"))
