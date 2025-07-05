import os
import openai
import anthropic
from google import genai
from google.genai import types as genai_types

import logging
import json

logger = logging.getLogger(__name__)


def _generate_structured_with_claude(system_prompt: str, user_prompt: str, model: str, max_tokens: int):
    """
    Calls Claude with instructions to return a structured JSON response using its tool-use feature.
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    logger.info(f"Generating structured response with Claude model {model}")
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

    #print("Sende Anfrage an Claude API...")
    response = client.messages.create(
        model=model,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        max_tokens=max_tokens,
        temperature=0.3,
        tools=[tool_schema],
        tool_choice={"type": "tool", "name": "update_content"}
    )

    tool_call_content = response.content[0].input
    new_content = tool_call_content['tool_input']['new_content']

    if not new_content:
        logger.error("Claude responded with valid JSON, but 'new_content' key was missing.")
        raise ValueError("AI failed to provide content in the expected format.")
    return new_content


def _generate_structured_with_gemini(system_prompt: str, user_prompt: str, model: str, max_tokens: int):
    """
    Calls Gemini with instructions to return a structured JSON response using its JSON mode.
    """
    logger.info(f"Generating structured response with Gemini model {model}")
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
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
    #print(response)
    try:
        response_json = json.loads(response.text)
        new_content = response_json.get("new_content")

        if not new_content:
            logger.error("Gemini responded with valid JSON, but 'new_content' key was missing.")
            raise ValueError("AI failed to provide content in the expected format.")
        return new_content
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from Gemini's response. Raw response: {response.text}. Error: {e}")
        raise ValueError("AI did not return valid JSON.")


def _generate_structured_with_local(system_prompt: str, user_prompt: str, model: str, max_tokens: int):
    """
    Calls a local OpenAI-compatible model with instructions to return a structured JSON response using its tool-use feature.
    """
    logger.info(f"Generating structured response with local model {model}")
    client = openai.OpenAI(base_url="http://localhost:1234/v1", api_key="not-needed")

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
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.3,
            tools=[tool_schema],
            # --- FIX: Use the string "required" as supported by local servers ---
            tool_choice="required"
        )

        # The model's response will be in the tool_calls section
        tool_call = response.choices[0].message.tool_calls[0]
        if tool_call.function.name == "update_content":
            # The arguments are a JSON string, so we need to parse them
            arguments = json.loads(tool_call.function.arguments)
            new_content = arguments.get("new_content")

            if not new_content:
                logger.error("Local model responded with valid JSON, but 'new_content' key was missing or empty.")
                raise ValueError("AI failed to provide content in the expected format.")
            return new_content
        else:
            logger.error(f"Local model called an unexpected tool: {tool_call.function.name}")
            raise ValueError("AI called an unexpected tool.")

    except (json.JSONDecodeError, IndexError, AttributeError) as e:
        logger.error(f"Failed to parse or find tool call in local model's response. Raw response: {response}. Error: {e}")
        raise ValueError("AI did not return a valid tool call in the expected format.")
    except openai.BadRequestError as e:
        logger.error(f"Local server returned a BadRequestError. This might be a model compatibility issue. Error: {e}")
        raise
    except Exception as e:
        # This will catch connection errors if the local server is not running
        logger.error(f"An unexpected error occurred while calling the local model: {e}")
        raise


def generate_structured_response(system_prompt: str, user_prompt: str, model: str = 'gemini-2.5-pro',
                                 max_tokens: int = 40960):
    """
    Ruft einen LLM auf mit der Anweisung, eine strukturierte JSON-Antwort zurückzugeben.
    Leitet die Anfrage an den entsprechenden Anbieter (Claude, Gemini oder Local) weiter.
    """
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
        raise


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
    logger.info(f"Initiating stream for model {model}")
    try:
        # The 'yield from' statement delegates the generation to the appropriate helper.
        if 'gpt' in model or model == 'local':
            yield from _generate_with_openai_streaming(messages, system_prompt, model, max_tokens)
        elif 'claude' in model:
            yield from _generate_with_claude_streaming(messages, system_prompt, model, max_tokens)
        elif 'gemini' in model:
            yield from _generate_with_gemini_streaming(messages, system_prompt, model, max_tokens)
        else:
            raise ValueError(f"Streaming not supported or model family unknown: {model}")
    except Exception as e:
        logger.error(f"Error during streaming with model {model}: {e}")
        # Re-raise the exception so the calling service (e.g., FastAPI) can handle it.
        raise


def _generate_with_openai_streaming(messages, system_prompt, model, max_tokens):
    """(FINAL) Handles streaming for OpenAI with simple, correct logic."""
    client_params = {"api_key": os.environ.get("OPENAI_API_KEY")}
    if model == 'local':
        client_params["base_url"] = "http://localhost:1234/v1"
        client_params["api_key"] = "not-needed"
    client = openai.OpenAI(**client_params)

    final_messages = [{"role": "system", "content": system_prompt}] + messages if system_prompt else messages
    stream = client.chat.completions.create(model=model, messages=final_messages, max_tokens=max_tokens,
                                            temperature=0.7, stream=True)

    for chunk in stream:
        content = chunk.choices[0].delta.content or ""
        # The simplest logic: just yield the content as it arrives.
        # This function will no longer filter <think> tags.
        # We will do that in the one place that calls this: the chatservice.
        if content:
            yield content


def _generate_with_claude_streaming(messages, system_prompt, model, max_tokens):
    """(FINAL) Handles streaming for Claude with simple, correct logic."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    with client.messages.stream(
            model=model,
            system=system_prompt,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.3,
    ) as stream:
        # Simply yield the text chunks as they come in.
        for text_chunk in stream.text_stream:
            if text_chunk:
                yield text_chunk


def _generate_with_gemini_streaming(messages, system_prompt, model, max_tokens):
    """(FINAL) Handles streaming for Gemini with simple, correct logic."""
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    contents = []
    for message in messages:
        role = 'user' if message['role'] == 'user' else 'model'
        contents.append(genai_types.Content(role=role, parts=[genai_types.Part.from_text(text=message['content'])]))

    generate_content_config = genai_types.GenerateContentConfig(
        max_output_tokens=max_tokens,
        temperature=0.7,
        system_instruction=system_prompt
    )


    for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
    ):
        try:
            if chunk.text:
                yield chunk.text
        except (ValueError, IndexError):
            continue