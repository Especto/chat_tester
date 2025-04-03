import asyncio
import datetime
import json
import os

from playwright.async_api import async_playwright

from config import USER_PROFILE, LOGIN_LINK, START_MESSAGE, CHAT_HISTORY
from gemini_model import generate_answer
from models import ChatMessage, UserMessage, UserModel

def get_log_filenames(chat_id):
    """Return filenames for logs based on chat_id"""
    json_log_file = f"logs/{chat_id}.json"
    log_file = f"logs/{chat_id}.logs"
    return json_log_file, log_file

def save_chat_logs(chat_id):
    """Save formatted logs to a text file based on chat_id"""
    json_log_file, log_file = get_log_filenames(chat_id)
    formatted_logs = []
    try:
        with open(json_log_file, 'r', encoding='utf-8') as f:
            logs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logs = []
        print(f"[save_chat_logs]: file {json_log_file} unavailable")

    for log in logs:
        sender = "🤖 User" if log["sender"] == "user" else "👩 Chat"
        text = log["text"] if log["text"] else "*No text*"
        has_image = "(PHOTO 📸)" if log.get("image") else ""
        has_star = "⭐" if log.get("send_star") else ""
        timestamp = datetime.datetime.fromisoformat(log["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
        formatted_logs.append(f"{sender}: {text} {has_image}{has_star} ({timestamp})")

    with open(log_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(formatted_logs))

async def save_log(log_data, chat_id):
    """Save a log entry to JSON file based on chat_id"""
    json_log_file, _ = get_log_filenames(chat_id)
    try:
        with open(json_log_file, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logs = []

    logs.append(log_data)

    with open(json_log_file, "w", encoding="utf-8") as f:
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


async def start_browser():
    playwright = await async_playwright().start()
    browser, page = await create_browser("browser_profile", playwright)
    return browser, page, playwright


async def get_message(page, chat_message: ChatMessage, chat_id) -> ChatMessage:
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
        }, chat_id)
        chat_message = message
        return chat_message


async def send_message(message: UserMessage, text_input, send_button, page, chat_id):
    if message.send_star:
        await send_button.click()
        await asyncio.sleep(1)

        send_stars_selector = r"//button[descendant::p[text()='Send stars']]"
        send_stars_bt = await page.wait_for_selector(send_stars_selector)
        await send_stars_bt.click()

    else:
        await text_input.fill(message.text)
        await asyncio.sleep(1)
        await text_input.press('Enter')

    await save_log({
        "sender": "user",
        "text": message.text if not message.send_star else None,
        "send_star": message.send_star,
        "timestamp": datetime.datetime.now().isoformat()
    }, chat_id)



async def parse_profile(page, link) -> UserModel:
    link = "https://golove.ai/character/" + link
    await page.goto(link)

    name_element = await page.wait_for_selector(r"body > main > div > div > div.bg-white\/\[4\%\].min-h-\[425px\].relative.h-full.max-h-\[425px\].w-full > div.flex.absolute.bg-\[\#0b0b0b\].bottom-\[-20px\].rounded-t-\[24px\].justify-between.gap-\[16px\].pt-\[20px\].w-full > div > div > h4")
    age_element = await page.wait_for_selector(r"body > main > div > div > div.bg-white\/\[4\%\].min-h-\[425px\].relative.h-full.max-h-\[425px\].w-full > div.flex.absolute.bg-\[\#0b0b0b\].bottom-\[-20px\].rounded-t-\[24px\].justify-between.gap-\[16px\].pt-\[20px\].w-full > div > div > h4 > span")
    bio_element = await page.wait_for_selector(r"body > main > div > div > div.flex.flex-col.mx-\[16px\].mt-\[48px\] > div.bg-white\/\[4\%\].rounded-\[16px\].p-\[16px\].flex.flex-col.gap-\[12px\] > p")

    name, age, bio = await name_element.text_content(), await age_element.text_content(), await bio_element.text_content()

    return UserModel(name=name, age=age, bio=bio)

async def get_token_from_cookies(page):

    cookies = await page.context.cookies()
    token_cookie = None
    for cookie in cookies:
        if cookie["name"] == "token":
            token_cookie = cookie
            break

    if token_cookie:
        token_value = token_cookie["value"]
        return token_value


async def run_test(page, iterations, chat_id, character_id):
    try:
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
        await asyncio.sleep(5)

        for _ in range(int(iterations)):
            await send_message(user_message, text_input, send_button, page, chat_id)
            print(f"🤖: {user_message.text} {user_message.send_star}")

            chat_message = await get_message(page, chat_message, chat_id)
            print(f"👩: {chat_message.text} {chat_message.image}")

            user_message = generate_answer(chat_message.text, USER_PROFILE, partner_profile, chat_message.image)

    except Exception as ex:
        print("[run_test]: ", ex)


def set_parameters():
    try:
        iterations = int(input("Enter the number of iterations: "))
        character_id = str(input("Character id: "))  # b8e4d2a3-56f9-7821-64c5-9bd0e83f0c23
        chat_id = str(input("Chat id: "))  # 9fa4eeef-9854-4b10-a61c-dcdd35edc892
    except:
        print("[set_parameters]: Incorrect data type")
        iterations, chat_id, character_id = set_parameters()

    return iterations, chat_id, character_id


async def main():

    browser, page, playwright = await start_browser()
    await page.goto(LOGIN_LINK)
    character_id, chat_id, iterations = None, None, None

    while True:
        print("\n1. Start test")
        print("2. Set parameters")
        print("3. Exit")

        choice = input("Choose an action: ")
        print()

        if choice == "1":
            if not character_id:
                print("Set the parameters first.")
                continue
            await run_test(page, iterations, chat_id, character_id)
            save_chat_logs(chat_id)
            print("\nChat logs saved")
        elif choice == "2":
            iterations, chat_id, character_id = set_parameters()
        elif choice == "3":
            await browser.close()
            break
        else:
            print("Invalid choice")

    await browser.close()
    await playwright.stop()

if __name__ == "__main__":
    asyncio.run(main())
