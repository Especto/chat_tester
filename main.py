import asyncio
import datetime
import json
import os

from playwright.async_api import async_playwright

from config import USER_PROFILE, LOGIN_LINK, START_MESSAGE, CHAT_HISTORY
from gemini_model import generate_answer
from models import ChatMessage, UserMessage, UserModel

JSON_LOG_FILE = "logs.json"
LOG_FILE = "logs.logs"


def save_chat_logs():
    try:
        formatted_logs = []
        with open(JSON_LOG_FILE, 'r', encoding='utf-8') as f:
            logs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"File {JSON_LOG_FILE} unavailable")

    for log in logs:
        sender = "🤖 User" if log["sender"] == "user" else "👩 Chat"
        text = log["text"] if log["text"] else "*No text*"
        has_image = "(PHOTO 📸)" if log.get("image") else ""
        has_star = "⭐" if log.get("send_star") else ""
        timestamp = datetime.datetime.fromisoformat(log["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
        formatted_logs.append(f"{sender}: {text} {has_image}{has_star} ({timestamp})")

    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(formatted_logs))


async def save_log(log_data):
    try:
        with open(JSON_LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logs = []

    logs.append(log_data)

    with open(JSON_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=4)


async def create_browser(profile_file, playwright):
    profile_dir = profile_file
    launch_args = {
        'user_data_dir': profile_dir,
        'headless': False
    }

    context = await playwright.chromium.launch_persistent_context(**launch_args)
    page = await context.new_page()
    return context, page


async def get_message(page, chat_message: ChatMessage) -> ChatMessage:
    while True:
        await asyncio.sleep(1.5)
        block_of_message = await page.query_selector(
            r"body > main > div.relative.overscroll-none.overflow-y-auto.w-full.z-\[15\].pb-\[24px\].pt-\[8px\].flex-1.h-full.mx-auto.px-\[16px\].allow-select > div > div:nth-child(1)")
        div_message = await block_of_message.query_selector('div.flex.justify-start')

        message = ChatMessage()

        if div_message:
            text_elements = await div_message.query_selector_all("p")
            if text_elements:
                message.text = await text_elements[0].text_content()
                message.time = await text_elements[1].text_content()

            img_element = await div_message.query_selector("img")
            if img_element:
                image_url = await img_element.get_attribute("src")
                if image_url != chat_message.image_url:
                    message.image = True
                    message.image_url = "https://golove.ai/" + image_url

        if (message.text == chat_message.text and message.time == chat_message.time) or not message.text:
            continue

        await save_log({
            "sender": "chat",
            "text": message.text,
            "image": message.image_url if message.image else None,
            "timestamp": datetime.datetime.now().isoformat()
        })
        chat_message = message
        return chat_message


async def send_message(page, message: UserMessage, text_input, send_button):
    if message.send_star:
        await send_button.click()
        await asyncio.sleep(1)
    else:
        await text_input.fill(message.text)
        await asyncio.sleep(1)
        await text_input.press('Enter')

    await save_log({
        "sender": "user",
        "text": message.text if not message.send_star else None,
        "send_star": message.send_star,
        "timestamp": datetime.datetime.now().isoformat()
    })


async def parse_profile(page, link) -> UserModel:
    link = "https://golove.ai/character/" + link
    await page.goto(link)

    name_age_element = await page.wait_for_selector(r"body > main > div > div.flex.justify-between.gap-\[16px\].w-full > div.flex.gap-\[16px\] > div > h4")
    bio_element = await page.wait_for_selector(r"body > main > div > div.bg-white\/\[4\%\].rounded-\[16px\].p-\[16px\].flex.flex-col.gap-\[8px\] > p")
    name_age = await name_age_element.text_content()
    name, age = name_age.split(' ')
    bio = await bio_element.text_content()

    return UserModel(name=name, age=age, bio=bio)


async def main():
    async with async_playwright() as playwright:
        try:
            browser, page = await create_browser("browser_profile", playwright)
            await page.goto(LOGIN_LINK)
            character_id = input("Character id: ")  # b951fec7-693e-4373-ac61-76f3036a3a5b
            chat_id = input("Chat id: ")  # 6045b863-7855-488b-ac26-eeb0b1deb529
            iterations = input("Number of messages: ")

            partner_profile = await parse_profile(page, character_id)
            print("Profile: ", partner_profile)

            await page.goto('https://golove.ai/chat/' + chat_id)

            text_input = await page.wait_for_selector(
                r"body > main > div:nth-child(3) > div > div.w-full.bg-white\/\[4\%\].border.border-white\/\[12\%\].hover\:border-white\/\[30\%\].focus-within\:border-white\/\[30\%\].transition-all.pt-\[8px\].px-\[16px\].rounded-\[16px\] > textarea")
            send_button = await page.wait_for_selector(
                r"body > main > div:nth-child(3) > div > div.flex.gap-\[16px\].items-end > div > button",
                state="visible")

            chat_message = ChatMessage()
            user_message = UserMessage(text=START_MESSAGE, send_star=False)

            CHAT_HISTORY.append({"role": "model", "parts": [user_message.text]})
            await asyncio.sleep(2)
            await send_message(page, user_message, text_input, send_button)
            for _ in range(int(iterations)):
                chat_message = await get_message(page, chat_message)
                print(f"👩: {chat_message.text} {chat_message.image}")

                user_message = generate_answer(chat_message.text, USER_PROFILE, partner_profile, chat_message.image)

                await send_message(page, user_message, text_input, send_button)
                print(f"🤖: {user_message.text} {user_message.send_star}")

            chat_message = await get_message(page, chat_message)
            print(f"👩: {chat_message.text} {chat_message.image}")
        except Exception as ex:
            print(ex)
            input("Press Enter to exit...")


if __name__ == "__main__":
    if os.path.exists(JSON_LOG_FILE):
        os.remove(JSON_LOG_FILE)
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    asyncio.run(main())
    save_chat_logs()