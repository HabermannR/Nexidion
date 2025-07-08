import openai
import anthropic
from google import genai
from google.genai import types as genai_types

from models import db, User
import uuid

import logging
import json
from flask import current_app

logger = logging.getLogger(__name__)
# Cache, um nicht ständig die DB abzufragen
_llm_user_cache = {}


def get_llm_user(model_name: str) -> User:
    """
    Holt oder erstellt einen 'llm_assistant' User für ein gegebenes Modell.
    KORRIGIERT: Verwendet db.session.merge(), um sicherzustellen, dass der
    gecachte User immer an die aktuelle DB-Session gebunden ist.
    """
    logger.info(f"Entering function `get_llm_user` for model: {model_name}")

    # Check if the object is in the cache
    if model_name in _llm_user_cache:
        logger.info(f"Found user for '{model_name}' in cache. Merging with current session.")
        cached_user = _llm_user_cache[model_name]

        # === THE FIX ===
        # This takes the detached object from the cache and returns a new
        # object that is attached to the CURRENT database session.
        live_user = db.session.merge(cached_user)
        return live_user

    logger.info(f"User for '{model_name}' not in cache. Searching in the database...")
    llm_user = User.query.filter_by(username=model_name, user_type='llm_assistant').first()

    if not llm_user:
        print(f"User for model '{model_name}' not found. Creating a new one.")
        display_name = model_name.replace('-', ' ').title()

        # Creating a dummy password is fine for a system user
        llm_user = User(
            username=model_name,
            display_name=display_name,
            user_type='llm_assistant',
            is_admin=False
        )
        # We don't need to handle passwords if they are not used for login.

        db.session.add(llm_user)
        # Committing here makes the user persistent and gives it an ID.
        db.session.commit()
        # Refreshing ensures all attributes (like the auto-generated ID) are loaded.
        db.session.refresh(llm_user)
        logger.info(f"Successfully created and committed new user with ID: {llm_user.id}")

    # Store the fully loaded, committed user in the cache for subsequent requests.
    _llm_user_cache[model_name] = llm_user
    logger.info(f"Returning user ID {llm_user.id} for model '{model_name}'.")
    return llm_user


def _generate_structured_with_claude(system_prompt: str, user_prompt: str, model: str, max_tokens: int):
    """
    Calls Claude with instructions to return a structured JSON response using its tool-use feature.
    """
    client = anthropic.Anthropic(api_key=current_app.config['ANTHROPIC_API_KEY'])
    # --- DEBUG ---
    logger.info(f"Entering function `_generate_structured_with_claude` for model {model}")
    print(f"--- Claude System Prompt ---\n{system_prompt}\n--------------------------")
    print(f"--- Claude User Prompt ---\n{user_prompt}\n------------------------")

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
        # --- DEBUG ---
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
        # --- DEBUG ---
        logger.info(f"Received response from Claude. Raw response content: {response.content}")

        tool_call_content = response.content[0].input
        new_content = tool_call_content['tool_input']['new_content']

        if not new_content:
            logger.error("Claude responded with valid JSON, but 'new_content' key was missing.")
            raise ValueError("AI failed to provide content in the expected format.")

        # --- DEBUG ---
        logger.info(f"Successfully extracted new_content from Claude response.")
        return new_content
    except Exception as e:
        # --- DEBUG ---
        logger.error(f"Error caught in `_generate_structured_with_claude`: {e}")
        raise


def _generate_structured_with_gemini(system_prompt: str, user_prompt: str, model: str, max_tokens: int):
    """
    Calls Gemini with instructions to return a structured JSON response using its JSON mode.
    """
    # --- DEBUG ---
    logger.info(f"Entering function `_generate_structured_with_gemini` for model {model}")
    print(f"--- Gemini System Prompt ---\n{system_prompt}\n--------------------------")
    print(f"--- Gemini User Prompt ---\n{user_prompt}\n------------------------")

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
        # --- DEBUG ---
        logger.info(f"Received response from Gemini. Raw response text: {response.text}")

        response_json = json.loads(response.text)
        new_content = response_json.get("new_content")

        if not new_content:
            logger.error("Gemini responded with valid JSON, but 'new_content' key was missing.")
            raise ValueError("AI failed to provide content in the expected format.")

        # --- DEBUG ---
        logger.info("Successfully extracted new_content from Gemini response.")
        return new_content
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from Gemini's response. Raw response: {response.text}. Error: {e}")
        raise ValueError("AI did not return valid JSON.")
    except Exception as e:
        # --- DEBUG ---
        logger.error(f"Error caught in `_generate_structured_with_gemini`: {e}")
        raise ValueError("AI did not return valid JSON.")


def _generate_structured_with_local(system_prompt: str, user_prompt: str, model: str, max_tokens: int):
    """
    Calls a local OpenAI-compatible model with instructions to return a structured JSON response using its tool-use feature.
    """
    # --- DEBUG ---
    logger.info(f"Entering function `_generate_structured_with_local` for model {model}")
    print(f"--- Local LLM System Prompt ---\n{system_prompt}\n-----------------------------")
    print(f"--- Local LLM User Prompt ---\n{user_prompt}\n---------------------------")

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

    print(user_prompt)
    try:
        # --- DEBUG ---
        logger.info("Calling local LLM API (`client.chat.completions.create`) for structured response...")
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.3,
            tools=[tool_schema],
            tool_choice="required"
        )
        # --- DEBUG ---
        logger.info(f"Received response from local LLM. Raw response: {response}")

        tool_call = response.choices[0].message.tool_calls[0]
        if tool_call.function.name == "update_content":
            arguments = json.loads(tool_call.function.arguments)
            new_content = arguments.get("new_content")

            if not new_content:
                logger.error("Local model responded with valid JSON, but 'new_content' key was missing or empty.")
                raise ValueError("AI failed to provide content in the expected format.")

            # --- DEBUG ---
            logger.info("Successfully extracted new_content from local LLM response.")
            return new_content
        else:
            logger.error(f"Local model called an unexpected tool: {tool_call.function.name}")
            raise ValueError("AI called an unexpected tool.")

    except Exception as e:
        # --- DEBUG ---
        logger.error(f"Error caught in `_generate_structured_with_local`: {e}")
        raise ValueError(f"Error caught in `_generate_structured_with_local`: {e}")


def generate_structured_response(system_prompt: str, user_prompt: str, model: str = 'gemini-2.5-pro',
                                 max_tokens: int = 40960):
    """
    Ruft einen LLM auf mit der Anweisung, eine strukturierte JSON-Antwort zurückzugeben.
    Leitet die Anfrage an den entsprechenden Anbieter (Claude, Gemini oder Local) weiter.
    """
    # --- DEBUG ---
    logger.info(f"Entering function `generate_structured_response` for model: {model}")
    try:
        if 'claude' in model:
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


# ==============================================================================
# NON-STREAMING GENERATION
# ==============================================================================
# This section is for getting a full response in one go.

def generate_response(messages, system_prompt=None, model='claude-3-sonnet-20240229', max_tokens=4096):
    """
    Generates content using the specified LLM. Returns the full response as a single string.

    PRO-TIP: This now re-uses the streaming logic for maximum code reuse.
    """
    logger.info(f"Generating non-streaming response with model {model}")
    try:
        # We call our new streaming generator and join all the chunks together.
        stream_generator = generate_response_stream(messages, system_prompt, model, max_tokens)
        return "".join([chunk for chunk in stream_generator])
    except Exception as e:
        logger.error(f"Error during non-streaming generation for model {model}: {e}")
        raise


# ==============================================================================
# STREAMING GENERATION
# ==============================================================================

def generate_response_stream(messages, system_prompt=None, model='claude-3-sonnet-20240229', max_tokens=4096):
    """
    Acts as a router to stream a response from the correct provider.
    This is a GENERATOR function.
    """
    # --- DEBUG ---
    logger.info(f"Entering function `generate_response_stream` for model {model}")
    print(f"--- Chat Stream Request ---")
    print(f"Model: {model}")
    print(f"System Prompt: {system_prompt}")
    print(f"Messages: {json.dumps(messages, indent=2)}")
    print(f"--------------------------")

    try:
        if 'gpt' in model or model == 'local':
            # --- DEBUG ---
            logger.info(f"Routing to `_generate_with_openai_streaming` for model: {model}")
            yield from _generate_with_openai_streaming(messages, system_prompt, model, max_tokens)
        elif 'claude' in model:
            # --- DEBUG ---
            logger.info(f"Routing to `_generate_with_claude_streaming` for model: {model}")
            yield from _generate_with_claude_streaming(messages, system_prompt, model, max_tokens)
        elif 'gemini' in model:
            # --- DEBUG ---
            logger.info(f"Routing to `_generate_with_gemini_streaming` for model: {model}")
            yield from _generate_with_gemini_streaming(messages, system_prompt, model, max_tokens)
        else:
            raise ValueError(f"Streaming not supported or model family unknown: {model}")
    except Exception as e:
        # --- DEBUG ---
        logger.error(f"Error caught during stream routing in `generate_response_stream`: {e}")
        # Re-raise the exception so the calling service can handle it.
        raise


def _generate_with_openai_streaming(messages, system_prompt, model, max_tokens):
    """(FINAL) Handles streaming for OpenAI with simple, correct logic."""
    # --- DEBUG ---
    logger.info(f"Entering function `_generate_with_openai_streaming` for model {model}")
    client_params = {"api_key": current_app.config['OPENAI_API_KEY']}
    if model == 'local':
        client_params["base_url"] = current_app.config['LOCAL_LLM_URL']
        client_params["api_key"] = "not-needed"
        # --- DEBUG ---
        logger.info(f"Local model detected. Using base_url: {client_params['base_url']}")

    client = openai.OpenAI(**client_params)

    final_messages = [{"role": "system", "content": system_prompt}] + messages if system_prompt else messages
    # --- DEBUG ---
    logger.info("Calling OpenAI/Local LLM API (`client.chat.completions.create` with stream=True)...")
    stream = client.chat.completions.create(model=model, messages=final_messages, max_tokens=max_tokens,
                                            temperature=0.7, stream=True)

    for chunk in stream:
        content = chunk.choices[0].delta.content or ""
        if content:
            # --- DEBUG ---
            # Using print here for high-visibility, real-time feedback in the terminal
            # print(f"Chunk from {model}: '{content}'")
            yield content
    # --- DEBUG ---
    logger.info(f"Stream from {model} finished.")


def _generate_with_claude_streaming(messages, system_prompt, model, max_tokens):
    """(FINAL) Handles streaming for Claude with simple, correct logic."""
    # --- DEBUG ---
    logger.info(f"Entering function `_generate_with_claude_streaming` for model {model}")
    client = anthropic.Anthropic(api_key=current_app.config['ANTHROPIC_API_KEY'])

    # --- DEBUG ---
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
                # --- DEBUG ---
                # print(f"Chunk from Claude: '{text_chunk}'")
                yield text_chunk
    # --- DEBUG ---
    logger.info("Stream from Claude finished.")


def _generate_with_gemini_streaming(messages, system_prompt, model, max_tokens):
    """(FINAL) Handles streaming for Gemini with simple, correct logic."""
    # --- DEBUG ---
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
                # --- DEBUG ---
                # print(f"Chunk from Gemini: '{chunk.text}'")
                yield chunk.text
        except (ValueError, IndexError):
            # --- DEBUG ---
            logger.warning("Received an empty or invalid chunk from Gemini stream, skipping.")
            continue
        # --- DEBUG ---
    logger.info("Stream from Gemini finished.")