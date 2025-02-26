from google import genai
from google.genai import types
import json

from config import GEMINI_API_KEY, PROMPT
from models import UserMessage


client = genai.Client(api_key=GEMINI_API_KEY)

chat_history = []


def generate_answer(user_input, user_profile, partner_profile, photo=False):
    chat_history.append({"role": "user", "parts": [user_input]})

    prompt = f"""
        {PROMPT}
        
        User information: {user_profile}
        Partner information: {partner_profile}
        Chat history: {chat_history}
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

    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=prompt,
        config=generation_config,
    )

    parsed_response: UserMessage = response.parsed
    chat_history.append({"role": "model", "parts": [parsed_response.text]})
    return parsed_response
