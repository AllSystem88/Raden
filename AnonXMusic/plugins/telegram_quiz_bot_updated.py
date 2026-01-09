from telethon import TelegramClient, events, functions, types, errors
from telethon.sessions import StringSession
import re, time, random, asyncio, logging

# ====== CONFIG ======
api_id = '12380656'
api_hash = 'd927c13beaaf5110f25c505b7c071273'
session_string = '1BZWaqwUAUHcMZHgOw1mq4wgKvV5-Fs9f7P6gSB5WsmXgMPM9yCRHmyrWs9isnGYieoJ1ZOCgm0lhw-LHIBpNQdPZvP7yvvx8NTtaQ3ibdeN3CHgCwJpHVUUR4pqYa7lN6hz07aGevM3iXWik8TujEAV6SQ4CY-s1twflbfYKypnK6Nrq1zYOC81GSXEU1jz0uXzc0JvCEN4zgzhV8bjsTFcGZN9OXn5dn74MAm8_M5cukVukr7zqmFi97tPDIOxtfOUFb7BYCGCKOiFaPERlOYrr5IL6fe6zXqzDcRAMbM8Nr_UbwVW5boTyMAAGL1q_gayhYqGIH8URgz1IVHAU2j8je-IWXw0='

# Required Channels (Only Usernames)
REQUIRED_CHANNELS = ['exampurrs', 'exampurss_official', 'FONT_CHANNEL_01']

client = TelegramClient(StringSession(session_string), api_id, api_hash)
target_chat = None

# ====== EMOJI REMOVAL LOGIC ======
emoji_pattern = re.compile("[" "\U0001F600-\U0001F64F" "\U0001F300-\U0001F5FF" "\U0001F680-\U0001F6FF" "\U0001F1E0-\U0001F1FF" "\U00002500-\U00002BEF" "\U00002702-\U000027B0" "\U00002712-\U00002716" "\U000024C2-\U0001F251" "\U0001f926-\U0001f937" "\U00010000-\U0010ffff" "\u2640-\u2642" "\u2600-\u2B55" "\u200d" "\u23cf" "\u23e9" "\u231a" "\ufe0f" "\u3030" "]+", flags=re.UNICODE)

def clean_text(twe: types.TextWithEntities) -> types.TextWithEntities:
    original_text = twe.text
    entities = twe.entities or []
    new_text = emoji_pattern.sub('', original_text)
    
    # Simple entity adjustment (Basic version for performance)
    new_entities = []
    for entity in entities:
        if entity.offset < len(new_text):
            new_entities.append(entity)
    return types.TextWithEntities(text=new_text, entities=new_entities)

# ====== SUBSCRIPTION CHECK ======
async def is_subscribed(user_id):
    for ch in REQUIRED_CHANNELS:
        try:
            await client(functions.channels.GetParticipantRequest(channel=ch, participant=user_id))
        except (errors.UserNotParticipantError, errors.ChannelPrivateError):
            return False
        except Exception:
            return False
    return True

# ====== COMMAND HANDLERS ======
@client.on(events.NewMessage(pattern='/pn'))
async def pn_handler(event):
    global target_chat
    if not await is_subscribed(event.sender_id):
        return await event.reply("⚠️ **𝐀𝐂𝐂𝐄𝐒𝐒 𝐃𝐄𝐍𝐈𝐄𝐃!**\n\nPehle ye channels join karo:\n👉 @exampurrs\n👉 @exampurss_official\n👉 @FONT_CHANNEL_01\n\nPhir se `/pn` likhna.")

    reply = await event.get_reply_message()
    if not reply: return await event.reply('Reply to a quiz share message.')

    quiz_id = None
    text = reply.text or ""
    if 't.me/QuizBot?start=' in text:
        quiz_id = re.search(r'start=([\w-]+)', text).group(1)
    elif reply.buttons:
        for row in reply.buttons:
            for btn in row:
                if hasattr(btn, 'url') and 't.me/QuizBot?start=' in btn.url:
                    match = re.search(r'start=([\w-]+)', btn.url)
                    if match: quiz_id = match.group(1)
    
    if not quiz_id: return await event.reply('Invalid quiz link.')

    target_chat = event.chat_id
    await client.send_message('QuizBot', '/stop')
    await asyncio.sleep(1)
    await client.send_message('QuizBot', f'/start {quiz_id}')

@client.on(events.NewMessage(from_users='QuizBot'))
async def quiz_handler(event):
    global target_chat
    if not target_chat: return
    
    msg = event.message
    if msg.buttons:
        for i, row in enumerate(msg.buttons):
            for j, btn in enumerate(row):
                if 'i am ready' in btn.text.lower():
                    await msg.click(i, j)
                    return

    if msg.poll and msg.poll.poll.quiz:
        # Vote and get correct answer
        options = [ans.option for ans in msg.poll.poll.answers]
        await client(functions.messages.SendVoteRequest(peer='QuizBot', msg_id=msg.id, options=[random.choice(options)]))
        await asyncio.sleep(2)
        
        updated = await client.get_messages('QuizBot', ids=msg.id)
        correct_option = next((res.option for res in updated.poll.results.results if res.correct), None)
        
        if correct_option is not None:
            # Clean question and answers
            q_clean = clean_text(types.TextWithEntities(text=updated.poll.poll.question.text, entities=updated.poll.poll.question.entities or []))
            ans_clean = [types.PollAnswer(text=clean_text(ans.text if isinstance(ans.text, types.TextWithEntities) else types.TextWithEntities(text=ans.text, entities=[])), option=ans.option) for ans in updated.poll.poll.answers]
            
            poll = types.Poll(id=int(time.time()), question=q_clean, answers=ans_clean, quiz=True, public_voters=False)
            media = types.InputMediaPoll(poll=poll, correct_answers=[correct_option])
            
            sent = await client.send_message(target_chat, file=media)
            await asyncio.sleep(1)
            # Close poll
            poll.closed = True
            await client(functions.messages.EditMessageRequest(peer=target_chat, id=sent.id, media=types.InputMediaPoll(poll=poll, correct_answers=[correct_option])))

@client.on(events.NewMessage(pattern='/stop'))
async def stop_handler(event):
    global target_chat
    await client.send_message('QuizBot', '/stop')
    target_chat = None
    await event.reply('Stopped.')

print("Userbot is running...")
with client:
    client.run_until_disconnected()
    
