from telethon import TelegramClient, events, functions, types, errors, Button
from telethon.sessions import StringSession
from pymongo import MongoClient
import asyncio
import random
import time
import logging
import re

# ================= LOGGING =================
logging.basicConfig(level=logging.INFO)

# ================= TELEGRAM API =================
api_id = 12380656
api_hash = "d927c13beaaf5110f25c505b7c071273"
bot_token = "7679920689:AAE0L-ChxmVVpEWJ5YMsj3Hygip9zm1tKF0"

client = TelegramClient(bottoken(bot_token), api_id, api_hash)

# ================= MONGODB =================
mongo = MongoClient("mongodb://localhost:27017")
db = mongo["quiz_bot"]
polls_col = db["polls"]

# ================= REQUIRED CHANNELS =================
# ONLY usernames (without @) OR numeric IDs
REQUIRED_CHANNELS = [
    "exampurrs",
    "exampurss_official",
    "FONT_CHANNEL_01",
    "sarakari_result"
]

target_chat = None

# ================= JOIN BUTTONS =================
def join_buttons():
    buttons = []
    for ch in REQUIRED_CHANNELS:
        if isinstance(ch, int):
            continue
        buttons.append([Button.url(f"Join {ch}", f"https://t.me/{ch}")])
    return buttons

def join_text():
    return "⚠️ **Pehle niche diye gaye sabhi channels join karo** 👇"

# ================= MEMBERSHIP CHECK =================
async def is_user_subscribed_to_all(user_id):
    for channel in REQUIRED_CHANNELS:
        try:
            entity = await client.get_entity(channel)
            await client(functions.channels.GetParticipantRequest(
                channel=entity,
                participant=user_id
            ))
        except errors.UserNotParticipantError:
            return False
        except errors.ChannelPrivateError:
            return False
        except Exception as e:
            logging.error(f"Join check error {channel}: {e}")
            return False
    return True

# ================= /pn =================
@client.on(events.NewMessage(pattern="/pn"))
async def pn_handler(event):
    global target_chat

    if not await is_user_subscribed_to_all(event.sender_id):
        await event.reply(
            join_text(),
            buttons=join_buttons(),
            link_preview=False
        )
        return

    reply = await event.get_reply_message()
    if not reply:
        await event.reply("Reply to QuizBot quiz link.")
        return

    quiz_id = None
    text = reply.text or ""

    if "t.me/QuizBot?start=" in text:
        quiz_id = re.search(r"start=([\w-]+)", text).group(1)

    if not quiz_id and reply.buttons:
        for row in reply.buttons:
            for btn in row:
                if btn.url and "t.me/QuizBot?start=" in btn.url:
                    quiz_id = re.search(r"start=([\w-]+)", btn.url).group(1)

    if not quiz_id:
        await event.reply("Invalid quiz format.")
        return

    target_chat = event.chat_id
    await client.send_message("QuizBot", "/stop")
    await asyncio.sleep(1)
    await client.send_message("QuizBot", f"/start {quiz_id}")

# ================= /stop =================
@client.on(events.NewMessage(pattern="/stop"))
async def stop_handler(event):
    global target_chat

    if not await is_user_subscribed_to_all(event.sender_id):
        await event.reply(join_text(), buttons=join_buttons())
        return

    await client.send_message("QuizBot", "/stop")
    target_chat = None
    await event.reply("Quiz stopped.")

# ================= QUIZ HANDLER =================
@client.on(events.NewMessage(from_users="QuizBot"))
async def quiz_handler(event):
    global target_chat
    if not target_chat:
        return

    msg = event.message

    # Ready button
    if msg.buttons:
        for i, row in enumerate(msg.buttons):
            for j, btn in enumerate(row):
                if "ready" in btn.text.lower():
                    await msg.click(i, j)
                    return

    if not (msg.poll and msg.poll.poll.quiz):
        return

    # Vote randomly
    option = random.choice([a.option for a in msg.poll.poll.answers])
    await client(functions.messages.SendVoteRequest(
        peer="QuizBot",
        msg_id=msg.id,
        options=[option]
    ))

    await asyncio.sleep(2)

    updated = await client.get_messages("QuizBot", ids=msg.id)

    correct_option = None
    for r in updated.poll.results.results:
        if r.correct:
            correct_option = r.option

    if not correct_option:
        return

    # ================= SAVE TO MONGO =================
    poll_data = {
        "poll_id": updated.id,
        "question": updated.poll.poll.question.text,
        "options": [a.text.text for a in updated.poll.poll.answers],
        "correct_option": correct_option.hex(),
        "created_at": time.time()
    }
    polls_col.insert_one(poll_data)

    # ================= SEND TO GROUP =================
    poll = types.Poll(
        id=int(time.time()),
        question=updated.poll.poll.question,
        answers=updated.poll.poll.answers,
        quiz=True,
        multiple_choice=False,
        public_voters=False
    )

    media = types.InputMediaPoll(
        poll=poll,
        correct_answers=[correct_option]
    )

    sent = await client.send_message(target_chat, file=media)

    await asyncio.sleep(1)

    poll.closed = True
    await client(functions.messages.EditMessageRequest(
        peer=target_chat,
        id=sent.id,
        media=media
    ))

# ================= RUN =================
with client:
    client.run_until_disconnected()
