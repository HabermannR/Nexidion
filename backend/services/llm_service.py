# backend/services/llm_service.py
# (Dies ist dein bereinigtes und umbenanntes llm.py)

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

# Cache, um nicht ständig die DB abzufragen. Nützlich in einem einzelnen Worker-Prozess.
_llm_user_cache = {}

def get_llm_user(model_name: str) -> User:
    """
    Holt oder erstellt einen 'llm_assistant' User für ein gegebenes Modell.
    Diese Funktion ist hier, da sie eng mit den LLM-Modellen verknüpft ist.
    """
    if model_name in _llm_user_cache:
        # 'merge' stellt sicher, dass das Objekt an die aktuelle DB-Session gebunden ist.
        return db.session.merge(_llm_user_cache[model_name])

    llm_user = User.query.filter_by(username=model_name, user_type='llm_assistant').first()
    if not llm_user:
        display_name = model_name.replace('-', ' ').title()
        if model_name.startswith('mock'):
            clean_model_name = model_name.replace('mock-', '').replace('-', ' ').title()
            display_name = f"Mock LLM ({clean_model_name})"

        llm_user = User(username=model_name, display_name=display_name, user_type='llm_assistant')
        db.session.add(llm_user)
        db.session.commit()
        db.session.refresh(llm_user)

    _llm_user_cache[model_name] = llm_user
    return llm_user

def _generate_structured_with_claude(system_prompt: str, user_prompt: str, model: str, max_tokens: int):
    """
    Calls Claude with instructions to return a structured JSON response using its tool-use feature.
    """
    client = anthropic.Anthropic(api_key=current_app.config['ANTHROPIC_API_KEY'])
    logger.info(f"Entering function `_generate_structured_with_claude` for model {model}")

    tool_schema = {
        "name": "update_content",
        "description": "Updates the content of a node with new, rewritten text. The output must be valid JSON.",
        "input_schema": {
            "type": "object",
            "properties": {"tool_input": {"type": "object", "properties": {
                "new_content": {"type": "string",
                                "description": "The full, rewritten content for the node goes here. Use proper Markdown formatting."}},
                                          "required": ["new_content"]}}, "required": ["tool_input"]
        }
    }
    try:
        logger.info("Calling Claude API (`client.messages.create`) for structured response...")
        response = client.messages.create(
            model=model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=max_tokens,
            temperature=0.3,
            tools=[tool_schema],
            tool_choice={"type": "tool", "name": "update_content"}
        )
        logger.info(f"Received response from Claude. Raw response content: {response.content}")

        tool_call_content = response.content[0].input
        new_content = tool_call_content['tool_input']['new_content']

        if not new_content:
            logger.error("Claude responded with valid JSON, but 'new_content' key was missing.")
            raise ValueError("AI failed to provide content in the expected format.")

        logger.info(f"Successfully extracted new_content from Claude response.")
        return new_content
    except Exception as e:
        logger.error(f"Error caught in `_generate_structured_with_claude`: {e}")
        raise


def _generate_structured_with_gemini(system_prompt: str, user_prompt: str, model: str, max_tokens: int):
    """
    Calls Gemini with instructions to return a structured JSON response using its JSON mode.
    """
    logger.info(f"Entering function `_generate_structured_with_gemini` for model {model}")

    client = genai.Client(
        api_key=current_app.config['GEMINI_API_KEY'],
    )

    contents = [
        genai_types.Content(
            role="user",
            parts=[
                genai_types.Part.from_text(text=user_prompt),
            ],
        ),
    ]
    generate_content_config = genai_types.GenerateContentConfig(
        thinking_config=genai_types.ThinkingConfig(
            thinking_budget=-1,
        ),
        response_mime_type="application/json",
        response_schema=genai_types.Schema(
            type=genai_types.Type.OBJECT,
            properties={
                "new_content": genai_types.Schema(
                    type=genai_types.Type.STRING,
                ),
            },
        ),
        system_instruction=[
            genai_types.Part.from_text(text=system_prompt),
        ],
    )

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=generate_content_config,
    )

    try:
        logger.info(f"Received response from Gemini. Raw response text: {response.text}")
        response_json = json.loads(response.text)
        new_content = response_json.get("new_content")

        if not new_content:
            logger.error("Gemini responded with valid JSON, but 'new_content' key was missing.")
            raise ValueError("AI failed to provide content in the expected format.")

        logger.info("Successfully extracted new_content from Gemini response.")
        return new_content
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from Gemini's response. Raw response: {response.text}. Error: {e}")
        raise ValueError("AI did not return valid JSON.")
    except Exception as e:
        logger.error(f"Error caught in `_generate_structured_with_gemini`: {e}")
        raise ValueError("AI did not return valid JSON.")


def _generate_structured_with_local(system_prompt: str, user_prompt: str, model: str, max_tokens: int):
    """
    Calls a local OpenAI-compatible model with instructions to return a structured JSON response using its tool-use feature.
    """
    logger.info(f"Entering function `_generate_structured_with_local` for model {model}")
    client = openai.OpenAI(base_url="http://192.168.2.59:1234/v1", api_key="not-needed")

    tool_schema = {
        "type": "function",
        "function": {
            "name": "update_content",
            "description": "Updates the content of a node with new, rewritten text. The output must be valid JSON.",
            "parameters": {
                "type": "object",
                "properties": {
                    "new_content": {
                        "type": "string",
                        "description": "The full, rewritten content for the node goes here. Use proper Markdown formatting."
                    }
                },
                "required": ["new_content"]
            }
        }
    }

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        logger.info("Calling local LLM API (`client.chat.completions.create`) for structured response...")
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.3,
            tools=[tool_schema],
            tool_choice="required"
        )
        logger.info(f"Received response from local LLM. Raw response: {response}")

        tool_call = response.choices[0].message.tool_calls[0]
        if tool_call.function.name == "update_content":
            arguments = json.loads(tool_call.function.arguments)
            new_content = arguments.get("new_content")

            if not new_content:
                logger.error("Local model responded with valid JSON, but 'new_content' key was missing or empty.")
                raise ValueError("AI failed to provide content in the expected format.")

            logger.info("Successfully extracted new_content from local LLM response.")
            return new_content
        else:
            logger.error(f"Local model called an unexpected tool: {tool_call.function.name}")
            raise ValueError("AI called an unexpected tool.")

    except Exception as e:
        logger.error(f"Error caught in `_generate_structured_with_local`: {e}")
        raise ValueError(f"Error caught in `_generate_structured_with_local`: {e}")


def generate_structured_response(system_prompt: str, user_prompt: str, model: str = 'gemini-2.5-pro',
                                 max_tokens: int = 40960):
    """
    Ruft einen LLM auf mit der Anweisung, eine strukturierte JSON-Antwort zurückzugeben.
    Leitet die Anfrage an den entsprechenden Anbieter (Claude, Gemini oder Local) weiter.
    """
    logger.info(f"Entering function `generate_structured_response` for model: {model}")
    try:
        if 'mock' in model:
            return _generate_structured_with_mock(system_prompt, user_prompt, model, max_tokens)
        elif 'claude' in model:
            return _generate_structured_with_claude(system_prompt, user_prompt, model, max_tokens)
        elif 'gemini' in model:
            return _generate_structured_with_gemini(system_prompt, user_prompt, model, max_tokens)
        elif 'local' in model:
            return _generate_structured_with_local(system_prompt, user_prompt, model, max_tokens)
        else:
            raise ValueError(
                f"Structured JSON response is not configured for model family: {model}. Supported families: 'claude', 'gemini', 'local'.")
    except Exception as e:
        logger.error(f"An unexpected error occurred in generate_structured_response: {e}")
        raise ValueError(f"An unexpected error occurred in generate_structured_response: {e}")


def generate_response(messages, system_prompt=None, model='claude-3-sonnet-20240229', max_tokens=10000):
    """
    Generates content using the specified LLM. Returns the full response as a single string.
    This re-uses the streaming logic for maximum code reuse.
    """
    logger.info(f"Generating non-streaming response with model {model}")
    try:
        # Hier wird der Generator sofort vollständig durchlaufen und die Teile zu einem String verbunden.
        stream_generator = generate_response_stream(messages, system_prompt, model, max_tokens)
        full_response = "".join(list(stream_generator))

        # Prüfen, ob der Stream einen Fehler zurückgegeben hat
        if "[ERROR in LLM Service:" in full_response:
            logger.error(f"Error during non-streaming generation for model {model}: {full_response}")
            raise RuntimeError(f"LLM service failed: {full_response}")

        return full_response

    except Exception as e:
        logger.error(f"Error during non-streaming generation for model {model}: {e}", exc_info=True)
        # Wirf den Fehler weiter, damit der aufrufende Code (z.B. Titelgenerierung) ihn behandeln kann.
        raise


def generate_response_stream(messages, system_prompt=None, model='claude-3-sonnet-20240229', max_tokens=10000):
    """
    Acts as a router to stream a response from the correct provider.
    This is a GENERATOR function that ALWAYS yields plain text chunks.
    """
    # Diese Log-Ausgabe wird jetzt den korrekten Modellnamen anzeigen
    logger.info(f"Entering function `generate_response_stream` for model '{model}'")

    generator_function = None
    try:
        # KORREKTUR 2: Überprüfe den ECHTEN 'model'-Parameter
        if model.startswith('mock'):
            generator_function = _mock_llm_stream_generator
        elif 'gpt' in model or model == 'local':
            generator_function = _generate_with_openai_streaming
        elif 'claude' in model:
            generator_function = _generate_with_claude_streaming
        elif 'gemini' in model:
            generator_function = _generate_with_gemini_streaming
        else:
            raise ValueError(f"Streaming not supported or model family unknown: {model}")

        logger.info(f"Router selected generator: {generator_function.__name__}")

        # KORREKTUR 3: Übergebe die Parameter korrekt
        if generator_function == _mock_llm_stream_generator:
            # Der Mock-Generator braucht nur das Modell
            stream = generator_function(model=model)  # <-- Übergebe den korrekten Modellnamen
        else:
            # Die anderen Generatoren brauchen alle Argumente
            stream = generator_function(
                messages=messages,
                system_prompt=system_prompt,
                model=model,  # <-- Übergebe den korrekten Modellnamen
                max_tokens=max_tokens
            )

        for chunk in stream:
            yield chunk

    except Exception as e:
        logger.error(f"Error during stream routing in `generate_response_stream`: {e}", exc_info=True)
        yield f"[ERROR in LLM Service: {str(e)}]"


def _generate_with_openai_streaming(messages, system_prompt, model, max_tokens):
    """Handles streaming for OpenAI with simple, correct logic."""
    logger.info(f"Entering function `_generate_with_openai_streaming` for model {model}")
    client_params = {"api_key": current_app.config['OPENAI_API_KEY']}
    if model == 'local':
        client_params["base_url"] = current_app.config['LOCAL_LLM_URL']
        client_params["api_key"] = "not-needed"
        logger.info(f"Local model detected. Using base_url: {client_params['base_url']}")

    client = openai.OpenAI(**client_params)

    final_messages = [{"role": "system", "content": system_prompt}] + messages if system_prompt else messages
    logger.info("Calling OpenAI/Local LLM API (`client.chat.completions.create` with stream=True)...")
    stream = client.chat.completions.create(model=model, messages=final_messages, max_tokens=max_tokens,
                                            temperature=0.7, stream=True)
    for chunk in stream:
        content = chunk.choices[0].delta.content or ""
        if content:
            yield content
    logger.info(f"Stream from {model} finished.")


def _generate_with_claude_streaming(messages, system_prompt, model, max_tokens):
    """Handles streaming for Claude with simple, correct logic."""
    logger.info(f"Entering function `_generate_with_claude_streaming` for model {model}")
    client = anthropic.Anthropic(api_key=current_app.config['ANTHROPIC_API_KEY'])
    logger.info("Calling Claude API (`client.messages.stream`)...")
    with client.messages.stream(
            model=model,
            system=system_prompt,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.3,
    ) as stream:
        for text_chunk in stream.text_stream:
            if text_chunk:
                yield text_chunk
    logger.info("Stream from Claude finished.")


def _generate_with_gemini_streaming(messages, system_prompt, model, max_tokens):
    """Handles streaming for Gemini with simple, correct logic."""
    logger.info(f"Entering function `_generate_with_gemini_streaming` for model {model}")
    client = genai.Client(api_key=current_app.config['GEMINI_API_KEY'])
    contents = []
    for message in messages:
        role = 'user' if message['role'] == 'user' else 'model'
        contents.append(genai_types.Content(role=role, parts=[genai_types.Part.from_text(text=message['content'])]))

    generate_content_config = genai_types.GenerateContentConfig(
        max_output_tokens=max_tokens,
        temperature=0.7,
        system_instruction=system_prompt
    )

    logger.info("Calling Gemini API (`client.models.generate_content_stream`)...")
    stream = client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    )
    for chunk in stream:
        try:
            if chunk.text:
                yield chunk.text
        except (ValueError, IndexError):
            logger.warning("Received an empty or invalid chunk from Gemini stream, skipping.")
            continue
    logger.info("Stream from Gemini finished.")


def _mock_llm_stream_generator(model: str = 'mock'):
    """
    A generator that simulates an LLM stream, yielding PLAIN TEXT chunks,
    just like the other real LLM generators.
    """
    if model == 'mock2':
        response_text = "Antwort von MOCK-MODELL-ZWEI. 🤖 Test für Modellwechsel erfolgreich!"
    else:
        response_text = "Antwort von MOCK-MODELL-EINS. 🤖 Dies ist die ursprüngliche Antwort."

    words = response_text.split()
    time.sleep(0.1)
    for word in words:
        # KORREKTUR: Gib nur den Text-String mit einem Leerzeichen zurück.
        yield f"{word} "
        time.sleep(random.uniform(0.05, 0.1))


def _generate_structured_with_mock(system_prompt: str, user_prompt: str, model: str, max_tokens: int):
    """
    Simulates a structured JSON response from the mock model for node proposals.
    """
    logger.info("🤖 MOCK MODEL: Generating a FAKE structured response for node proposal.")
    time.sleep(0.2)
    mock_new_content = (
        """Based on our discussion about project goals and quality, the team roles can now be defined.
- **Project Lead:** Responsible for overall delivery.\n
- **Technical Lead:** Ensures high-quality code and architecture.\n
- **QA Specialist:** Focuses on testing and quality assurance."""
    )
    return mock_new_content


def generate_chat_title(chat_history: str, model: str) -> str:
    """Generiert einen kurzen, prägnanten Titel für einen Chat-Verlauf."""
    system_prompt = "Based on the following conversation, create a very short, concise title (4-6 words max). The title should summarize the main topic. Respond with ONLY the title and nothing else."

    # Nutze die bestehende generate_response Funktion
    # Du kannst hier auch ein kleineres, schnelleres Modell verwenden
    title_model = 'gemini-2.5-flash'  # oder ein anderes
    try:
        # Wir nehmen nur die ersten paar Nachrichten für die Effizienz
        short_history = chat_history[:1500]
        response = generate_response(
            messages=[{"role": "user", "content": short_history}],
            system_prompt=system_prompt,
            model=title_model
        )
        return response.strip().replace('"', '')
    except Exception as e:
        logger.error(f"Could not generate chat title: {e}")
        return "Chat about Topic"