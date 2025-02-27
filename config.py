import json
from models import UserModel


def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)


config = load_config()
GEMINI_API_KEY = config["gemini_key"]
PROMPT = config["prompt"]
USER_PROFILE = UserModel(**config["user_profile"])
LOGIN_LINK = config["login_link"]
START_MESSAGE = config["start_message"]

CHAT_HISTORY = []

