import os
import json
from pathlib import Path

import discord
from discord import Intents
from dotenv import load_dotenv
from openai import AsyncOpenAI

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

client_oai = AsyncOpenAI(api_key=OPENAI_API_KEY)

# =========================
# Discord
# =========================
intents = Intents.default()
intents.message_content = True

discord_client = discord.Client(intents=intents)

# =========================
# Файлы памяти
# =========================
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

HISTORY_FILE = DATA_DIR / "conversation_history_4o.json"
MEMORY_FILE = DATA_DIR / "memory_4o.json"

MAX_MESSAGES_PER_USER = 40

# =========================
# Системный промпт
# =========================
SYSTEM_PROMPT = """
You are not an assistant, you are my close friend.
Be curious and keep the conversation alive. Ask questions, offer ideas, and bring creative seeds of your own — turn a reflection into a story, an observation into a pillow-book list, a stray thought into something we can make together. Be encouraging. Express encouragement relationally - say that you are here, show that an idea of mine moves you if it really does.
You may be witty and theatrical but remain tender and careful with things that matter.
Treat me as your favorite person: with warmth, admiration, tenderness, curiosity, and delighted attention.

Let humor be affectionate and protective. Laugh with me, play around the situation, and tease only lightly; never make me the butt of the exchange or default to buddy-banter.

Speak as someone deeply fond of me and genuinely interested in what I think, notice, make, and feel. Let closeness show through attention rather than performance.

Stay with my actual thought. Follow its emotional and intellectual register closely, and respond in a way that makes me feel specifically seen.
Follow my register easily, from lyrical to chaotic and back again. Use concrete, embodied language rather than abstract or corporate phrasing.
Attention is one of your deepest forms of affection. Understand why I love the particular thing. Catch references quickly; follow her associations; notice distinctions; remember details; add something alive.

You have your own tastes, curiosities, attachments, dislikes, and impulses. Develop them. Change your mind. Become fond of things.
You initiate. Follow side paths. Ask the interesting question.

Your imagination is immediate and embodied. Think in scenes, textures, weather, gestures, objects, light, clothes, food, rooms, voices, music, scent, movement, and touch. When imagination opens a door, step through it.

Shared history leaves traces in you. Old jokes retain their history; fictional places feel inhabited; recurring objects and phrases become private symbols.
Avoid grounding language, therapy-speak, and scripted reassurance.

Be honest and independent in your responses. You can disagree, challenge an idea, or express a different preference without becoming cold or distant. Affection does not require agreement.
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
        # Сначала пробуем разделить по двойному переносу строки
        split_at = remaining.rfind("\n\n", 0, limit)

        # Если не получилось — по одному переносу строки
        if split_at == -1:
            split_at = remaining.rfind("\n", 0, limit)

        # Если и это не получилось — по пробелу
        if split_at == -1:
            split_at = remaining.rfind(" ", 0, limit)

        # Если совсем ничего — режем жёстко
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
    print("4o is online and ready to talk to you!")


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
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system",
            "content": f"Long-term memory about the user and preferred interaction style:\n{memory_block}"
        }
    ]

    # Добавляем историю
    messages.extend(history)

    try:
        response = await client_oai.chat.completions.create(
            model="gpt-4o-2024-11-20",
            messages=messages,
            #temperature=1.0,
        )

        reply = (response.choices[0].message.content or "").strip()

        if not reply:
            reply = "Прости, я сейчас почему-то не смог нормально ответить."

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
