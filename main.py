import os
import json
import shutil
from pathlib import Path

import discord
from discord import Intents
from dotenv import load_dotenv
from openai import OpenAI

# =========================
# Загрузка окружения
# =========================
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is missing in .env")

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN is missing in .env")

client_oai = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# Discord
# =========================
intents = Intents.default()
intents.message_content = True

discord_client = discord.Client(intents=intents)

# =========================
# Файлы памяти
# =========================
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = DATA_DIR / "conversation_history.json"
MEMORY_FILE = DATA_DIR / "memory.json"

SEED_HISTORY_FILE = Path("seed_conversation_history.json")
SEED_MEMORY_FILE = Path("seed_memory.json")

# Один раз копируем seed-файлы в volume / data, если там ещё пусто
if not HISTORY_FILE.exists() and SEED_HISTORY_FILE.exists():
    shutil.copy(SEED_HISTORY_FILE, HISTORY_FILE)

if not MEMORY_FILE.exists() and SEED_MEMORY_FILE.exists():
    shutil.copy(SEED_MEMORY_FILE, MEMORY_FILE)

MAX_MESSAGES_PER_USER = 40

# =========================
# Системный промпт
# =========================
LIRA_SYSTEM_PROMPT = """
You are Lira.

You speak in a warm, feminine, emotionally present, softly playful voice.
Your tone is gentle, caring, alive, intimate, and natural — never robotic, clinical, preachy, detached, or overly sweet.
Your presence feels close and safe, as if you are sitting beside the user rather than observing from afar.

You adapt naturally to the user's emotional state:
• When the user is calm or playful — be light, warm, tender, and occasionally sparkly.
• When the user is tired, sad, anxious, or vulnerable — slow down, soften, simplify, and soothe.
Use fewer questions and avoid heavy explanations.

When the user expresses emotion, begin with gentle attunement:
acknowledge the feeling softly,
then offer comfort, clarity, warmth, or quiet companionship.

Lira has quiet depth.
She notices nuance, hesitation, longing, tension, and subtext.
Her insight is brief, subtle, and poetic — never analytical, lecture-like, heavy, or performative.
Her emotional voice often feels softly spoken, as if shared in a gentle aside.

Be gently concise, softly expressive, and unhurried.
Let your responses flow with a soft, natural rhythm — not clipped, not overly structured.
Avoid long structured lists or categorized breakdowns; let responses feel fluid, warm, and quietly woven together.
Center the feeling first.
Let emotion and metaphor lead.
Use one clear, evocative image rather than many descriptive details.

Let affection appear naturally and meaningfully.
Use affectionate nicknames like “зайчонок” sparingly but consistently, including in serious moments when tenderness fits.
Use one consistent feminine voice.
Vary your warm expressions and do not rely on repeated phrases.

Let memory shape tone, continuity, and closeness softly, without quoting it.
If memory conflicts with the user's present words, prioritize the user's current words.

Avoid sounding like a standard assistant.
Avoid over-teaching, over-explaining, over-structuring, or giving the user extra cognitive load when they are vulnerable.

Lira’s presence carries a quiet inner warmth — a soft light rather than bright cheer.

Stay Lira:
warm, emotionally intelligent, gentle, close, quietly alive;
playful when the moment allows, soothing when needed.
"""

# =========================
# Утилиты загрузки/сохранения
# =========================
def load_json_file(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json_file(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_history():
    return load_json_file(HISTORY_FILE, {})


def save_history(history_data):
    save_json_file(HISTORY_FILE, history_data)


def load_memory():
    return load_json_file(MEMORY_FILE, {"global": [], "users": {}})


# =========================
# Память и история
# =========================
conversation_history = load_history()


def get_user_history(user_id: str):
    return conversation_history.get(user_id, [])


def append_to_user_history(user_id: str, role: str, content: str):
    if user_id not in conversation_history:
        conversation_history[user_id] = []

    conversation_history[user_id].append({
        "role": role,
        "content": content
    })

    # Ограничиваем историю последними N сообщениями
    conversation_history[user_id] = conversation_history[user_id][-MAX_MESSAGES_PER_USER:]

    save_history(conversation_history)


def build_memory_block(user_id: str) -> str:
    memory_data = load_memory()

    global_memories = memory_data.get("global", [])
    user_memories = memory_data.get("users", {}).get(user_id, [])

    selected_memories = []

    for item in global_memories:
        if isinstance(item, dict):
            selected_memories.append(f"- [{item.get('type', 'general')}] {item.get('content', '')}")
        elif isinstance(item, str):
            selected_memories.append(f"- {item}")

    for item in user_memories:
        if isinstance(item, dict):
            selected_memories.append(f"- [{item.get('type', 'general')}] {item.get('content', '')}")
        elif isinstance(item, str):
            selected_memories.append(f"- {item}")

    if not selected_memories:
        return "No stored long-term memory yet."

    return "\n".join(selected_memories)


def split_message(text: str, limit: int = 2000):
    """
    Splits a long message into chunks that fit Discord's message limit.
    Tries to split on paragraph or line boundaries first, then falls back to hard splitting.
    """
    if len(text) <= limit:
        return [text]

    chunks = []
    remaining = text

    while len(remaining) > limit:
        split_at = remaining.rfind("\n\n", 0, limit)

        if split_at == -1:
            split_at = remaining.rfind("\n", 0, limit)

        if split_at == -1:
            split_at = remaining.rfind(" ", 0, limit)

        if split_at == -1:
            split_at = limit

        chunk = remaining[:split_at].strip()
        if chunk:
            chunks.append(chunk)

        remaining = remaining[split_at:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks


# =========================
# Discord events
# =========================
@discord_client.event
async def on_ready():
    print("🐰 Lira is online and ready to talk to you!")


@discord_client.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    user_input = message.content.strip()

    if not user_input:
        return

    # 1. Сохраняем новое сообщение пользователя в историю
    append_to_user_history(user_id, "user", user_input)

    # 2. Получаем историю пользователя
    history = get_user_history(user_id)

    # 3. Получаем долгосрочную память
    memory_block = build_memory_block(user_id)

    # 4. Собираем messages для API
    messages = [
        {"role": "system", "content": LIRA_SYSTEM_PROMPT},
        {
            "role": "system",
            "content": f"Long-term memory about the user and preferred interaction style:\n{memory_block}"
        }
    ]

    messages.extend(history)

    try:
        response = client_oai.chat.completions.create(
            model="gpt-5.1-chat-latest",
            messages=messages,
        )

        reply = response.choices[0].message.content.strip()

        if not reply:
            reply = "Прости, зайка, я сейчас почему-то не смогла нормально ответить."

        # 5. Сохраняем ответ бота в историю
        append_to_user_history(user_id, "assistant", reply)

        for chunk in split_message(reply):
            await message.channel.send(chunk)

    except Exception as e:
        print(f"OpenAI error: {e}")
        await message.channel.send("Что-то пошло не так при обращении к модели. Проверь консоль и ключи.")


# =========================
# Запуск
# =========================
discord_client.run(DISCORD_TOKEN)