# backend/services/llm_service.py
# FINALE, KORRIGIERTE VERSION

import openai
import anthropic
from google import genai
from google.genai import types as genai_types
import time, random
import logging
import json
from flask import current_app

from backend.models import db, User

logger = logging.getLogger(__name__)

_llm_user_cache = {}


# --- Schema-Definitionen für verschiedene Anwendungsfälle ---
def get_content_update_schema(provider: str):
    if provider == 'gemini':
        return genai_types.Schema(
            type=genai_types.Type.OBJECT,
            properties={"new_content": genai_types.Schema(type=genai_types.Type.STRING)},
            required=["new_content"]
        )
    else:
        return {"name": "update_content", "description": "Updates node content.",
            "input_schema": {"type": "object", "properties": {"new_content": {"type": "string"}},
                             "required": ["new_content"]}}


def get_title_generation_schema(provider: str):
    if provider == 'gemini':
        return genai_types.Schema(
            type=genai_types.Type.OBJECT,
            properties={"title": genai_types.Schema(type=genai_types.Type.STRING)},
            required=["title"]
        )
    else:
        return {"name": "create_chat_title", "description": "Creates a chat title.",
            "input_schema": {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}}


def get_llm_user(model_name: str) -> User:
    if model_name in _llm_user_cache: return db.session.merge(_llm_user_cache[model_name])
    llm_user = User.query.filter_by(username=model_name, user_type='llm_assistant').first()
    if not llm_user:
        display_name = model_name.replace('-', ' ').title()
        if 'local' in model_name:
            display_name = f"Local LLM ({display_name})"
        elif model_name.startswith('mock'):
            clean_model_name = model_name.replace('mock-', '').replace('-', ' ').title()
            display_name = f"Mock LLM ({clean_model_name})"
        llm_user = User(username=model_name, display_name=display_name, user_type='llm_assistant')
        db.session.add(llm_user);
        db.session.commit();
        db.session.refresh(llm_user)
    _llm_user_cache[model_name] = llm_user
    return llm_user


# --- GENERISCHE FUNKTION FÜR STRUKTURIERTE AUSGABEN ---
def generate_json_response(system_prompt: str, user_prompt: str, model: str, schema_generator: callable,
                           max_tokens: int = 4096):
    logger.info(f"Generating structured JSON with model {model} using schema from {schema_generator.__name__}")
    try:
        if 'claude' in model:
            tool_schema = schema_generator('claude')
            return _generate_json_with_claude(system_prompt, user_prompt, model, max_tokens, tool_schema)
        elif 'gemini' in model:
            response_schema = schema_generator('gemini')
            return _generate_json_with_gemini(system_prompt, user_prompt, model, max_tokens, response_schema)
        elif 'gpt' in model or 'local' in model:
            tool_schema = schema_generator('openai')
            return _generate_json_with_openai_compatible(system_prompt, user_prompt, model, max_tokens, tool_schema)
        else:
            raise ValueError(f"JSON response not configured for model family: {model}")
    except Exception as e:
        logger.error(f"Failed to generate structured JSON with {model}: {e}", exc_info=True)
        raise


# --- Private Implementierungen für die jeweiligen Anbieter ---
def _generate_json_with_claude(system_prompt, user_prompt, model, max_tokens, tool_schema):
    client = anthropic.Anthropic(api_key=current_app.config['ANTHROPIC_API_KEY'])
    response = client.messages.create(
        model=model, system=system_prompt, messages=[{"role": "user", "content": user_prompt}],
        max_tokens=max_tokens, temperature=0.2, tools=[tool_schema],
        tool_choice={"type": "tool", "name": tool_schema['name']}
    )
    if response.content and response.content[0].type == 'tool_use': return response.content[0].input
    raise ValueError("Claude did not return a valid tool call.")


def _generate_json_with_gemini(system_prompt, user_prompt, model, max_tokens, response_schema):
    """KORREKTE VERSION: Verwendet den Parameter 'config'."""
    client = genai.Client(api_key=current_app.config['GEMINI_API_KEY'])
    config_obj = genai_types.GenerateContentConfig(
        max_output_tokens=max_tokens,
        temperature=0.2,
        response_mime_type="application/json",
        response_schema=response_schema,
        system_instruction=[genai_types.Part.from_text(text=system_prompt)] if system_prompt else None
    )
    response = client.models.generate_content(
        model=model,
        contents=[genai_types.Part.from_text(text=user_prompt)],
        config=config_obj  # <-- KORREKTER PARAMETERNAME IST 'config'
    )
    return json.loads(response.text)


def _generate_json_with_openai_compatible(system_prompt, user_prompt, model, max_tokens, tool_schema):
    if 'local' in model:
        client = openai.OpenAI(base_url=current_app.config['LOCAL_LLM_URL'], api_key="not-needed")
        tool_choice = "required"
    else:
        client = openai.OpenAI(api_key=current_app.config.get('OPENAI_API_KEY'))
        tool_choice = {"type": "function", "function": {"name": tool_schema['name']}}
    openai_tool = {"type": "function",
                   "function": {"name": tool_schema['name'], "description": tool_schema['description'],
                                "parameters": tool_schema['input_schema']}}
    response = client.chat.completions.create(
        model=model, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        max_tokens=max_tokens, temperature=0.2, tools=[openai_tool], tool_choice=tool_choice
    )
    if not response.choices or not response.choices[0].message.tool_calls: raise ValueError(
        "OpenAI/Local compatible model did not return a tool call.")
    tool_call = response.choices[0].message.tool_calls[0]
    if tool_call.function.name == tool_schema['name']: return json.loads(tool_call.function.arguments)
    raise ValueError(f"Model called unexpected tool: {tool_call.function.name}")


# --- Öffentliche API-Funktionen (Wrapper) ---
def generate_structured_response(system_prompt: str, user_prompt: str, model: str, max_tokens: int = 4096):
    logger.info(f"Requesting content update with model {model}")
    if 'mock' in model: return "Mock content"
    response_data = generate_json_response(system_prompt, user_prompt, model, get_content_update_schema, max_tokens)
    content = response_data.get("new_content")
    if not content: raise ValueError("AI response did not contain 'new_content' key.")
    return content


def generate_chat_title(chat_history: str, model: str, max_tokens: int = 100) -> str:
    system_prompt = "Based on the conversation, create a short, concise title (4-6 words max). Use the provided tool."
    chosen_model = model or current_app.config.get('DEFAULT_CHAT_MODEL', 'gemini-1.5-flash')
    if "gemini" in chosen_model:
        chosen_model = 'gemini-1.5-flash'
    elif "claude" in chosen_model:
        chosen_model = 'claude-3-haiku-20240307'
    elif "gpt" in chosen_model:
        chosen_model = 'gpt-4o-mini'
    try:
        short_history = chat_history[:1500]
        response_data = generate_json_response(system_prompt, short_history, chosen_model, get_title_generation_schema,
                                               max_tokens)
        title = response_data.get("title")
        if not title: raise ValueError("AI response did not contain 'title' key.")
        return title.strip().replace('"', '')
    except Exception as e:
        logger.error(f"Could not generate structured chat title with model {chosen_model}: {e}")
        return "Chat about Topic"


# --- STREAMING FUNKTIONEN ---
def generate_response(messages, system_prompt=None, model='claude-3-sonnet-20240229', max_tokens=10000):
    try:
        stream_generator = generate_response_stream(messages, system_prompt, model, max_tokens)
        return "".join(list(stream_generator))
    except Exception as e:
        logger.error(f"Error during non-streaming generation for model {model}: {e}", exc_info=True)
        raise


def generate_response_stream(messages, system_prompt=None, model='claude-3-sonnet-20240229', max_tokens=10000):
    logger.info(f"Entering function `generate_response_stream` for model '{model}'")
    try:
        if model.startswith('mock'):
            generator_function = _mock_llm_stream_generator
        elif 'gpt' in model or 'local' in model:
            generator_function = _generate_with_openai_streaming
        elif 'claude' in model:
            generator_function = _generate_with_claude_streaming
        elif 'gemini' in model:
            generator_function = _generate_with_gemini_streaming
        else:
            raise ValueError(f"Streaming not supported for model family: {model}")

        stream = generator_function(messages=messages, system_prompt=system_prompt, model=model,
                                    max_tokens=max_tokens) if generator_function != _mock_llm_stream_generator else generator_function(
            model=model)
        for chunk in stream: yield chunk
    except Exception as e:
        logger.error(f"Error during stream routing in `generate_response_stream`: {e}", exc_info=True)
        yield f"[ERROR in LLM Service: {str(e)}]"


def _generate_with_openai_streaming(messages, system_prompt, model, max_tokens):
    client_params = {"api_key": current_app.config['OPENAI_API_KEY']}
    if 'local' in model:
        client_params["base_url"] = current_app.config['LOCAL_LLM_URL'];
        client_params["api_key"] = "not-needed"
    client = openai.OpenAI(**client_params)
    final_messages = [{"role": "system", "content": system_prompt}] + messages if system_prompt else messages
    stream = client.chat.completions.create(model=model, messages=final_messages, max_tokens=max_tokens,
                                            temperature=0.7, stream=True)
    for chunk in stream:
        if content := chunk.choices[0].delta.content: yield content


def _generate_with_claude_streaming(messages, system_prompt, model, max_tokens):
    client = anthropic.Anthropic(api_key=current_app.config['ANTHROPIC_API_KEY'])
    with client.messages.stream(model=model, system=system_prompt, messages=messages, max_tokens=max_tokens,
                                temperature=0.3) as stream:
        for text_chunk in stream.text_stream:
            if text_chunk: yield text_chunk


def _generate_with_gemini_streaming(messages, system_prompt, model, max_tokens):
    """
    FINALE KORREKTE VERSION für Streaming.
    Das 'contents'-Format ist jetzt korrekt als Liste von Content-Objekten.
    """
    logger.info(f"Entering function `_generate_with_gemini_streaming` for model {model}")
    client = genai.Client(api_key=current_app.config['GEMINI_API_KEY'])

    # KORREKTUR: Das ist das richtige Format für einen Chat-Verlauf.
    # Wir erstellen eine Liste von Content-Objekten.
    contents = []
    for msg in messages:
        role = 'user' if msg['role'] == 'user' else 'model'
        # Jede Nachricht wird ein genai.types.Content-Objekt
        contents.append(genai_types.Content(role=role, parts=[genai_types.Part.from_text(text=msg['content'])]))

    # Die Konfiguration bleibt wie sie war, sie ist korrekt.
    config_obj = genai_types.GenerateContentConfig(
        max_output_tokens=max_tokens,
        temperature=0.7,
        system_instruction=genai_types.Part.from_text(text=system_prompt) if system_prompt else None
    )

    logger.info("Calling Gemini API (`client.models.generate_content_stream`)...")

    stream = client.models.generate_content_stream(
        model=model,
        contents=contents,  # <-- `contents` hat jetzt das korrekte Format
        config=config_obj
    )

    for chunk in stream:
        try:
            if chunk.text:
                yield chunk.text
        except (ValueError, IndexError):
            logger.debug("Skipping empty or invalid chunk from Gemini stream.")
            continue
    logger.info("Stream from Gemini finished.")


def _mock_llm_stream_generator(model: str = 'mock'):
    response_text = "Antwort von MOCK-MODELL-ZWEI. 🤖" if model == 'mock2' else "Antwort von MOCK-MODELL-EINS. 🤖"
    for word in response_text.split():
        yield f"{word} ";
        time.sleep(random.uniform(0.05, 0.1))