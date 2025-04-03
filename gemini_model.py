import time

from google import genai
from google.genai import types
import json

from config import GEMINI_API_KEY, PROMPT, CHAT_HISTORY
from models import UserMessage


client = genai.Client(api_key=GEMINI_API_KEY)


def generate_answer(user_input, user_profile, partner_profile, photo=False):
    CHAT_HISTORY.append({"role": "user", "parts": [user_input]})

    prompt = f"""
        {PROMPT}
        
        User information: {user_profile}
        Partner information: {partner_profile}
        Chat history: {CHAT_HISTORY}
        User text: {user_input}
        Photo: {photo}

        Return the answer in JSON format, corresponding to the ChatResponse schema:
        {json.dumps(UserMessage.model_json_schema(), indent=2)}
        """

    generation_config = types.GenerateContentConfig(
        temperature=0.9,
        top_p=1,
        top_k=1,
        max_output_tokens=2048,
        safety_settings=[
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=types.HarmBlockThreshold.BLOCK_NONE
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE
            ),
        ],
        response_mime_type='application/json',
        response_schema=UserMessage,
    )
    retries = 7
    delay = 1
    for i in range(retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config=generation_config,
            )
            parsed_response: UserMessage = response.parsed
            CHAT_HISTORY.append(
                {"role": "model", "parts": [parsed_response.text if not parsed_response.send_star else "Sent star"]})
            return parsed_response
        except Exception as e:
            if i < retries - 1:
                print(f"[generate_answer] Error 503, retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2
            else:
                raise e

