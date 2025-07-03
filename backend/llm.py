import os
import openai
import anthropic
from google import genai
from google.genai import types

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
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=user_prompt),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            thinking_budget=-1,
        ),
        response_mime_type="application/json",
        response_schema=genai.types.Schema(
            type=genai.types.Type.OBJECT,
            properties={
                "new_content": genai.types.Schema(
                    type=genai.types.Type.STRING,
                ),
            },
        ),
        system_instruction=[
            types.Part.from_text(text=system_prompt),
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


def generate_structured_response(system_prompt: str, user_prompt: str, model: str = 'gemini-2.5-pro',
                                 max_tokens: int = 40960):
    """
    Ruft einen LLM auf mit der Anweisung, eine strukturierte JSON-Antwort zurückzugeben.
    Leitet die Anfrage an den entsprechenden Anbieter (Claude oder Gemini) weiter.
    """
    print(model)
    try:
        if 'claude' in model:
            return _generate_structured_with_claude(system_prompt, user_prompt, model, max_tokens)
        elif 'gemini' in model:
            return _generate_structured_with_gemini(system_prompt, user_prompt, model, max_tokens)
        else:
            raise ValueError(
                f"Structured JSON response is not configured for model family: {model}. Supported families: 'claude', 'gemini'.")
    except Exception as e:
        logger.error(f"An unexpected error occurred in generate_structured_response: {e}")
        raise

def _generate_with_openai(messages, system_prompt, model, max_tokens):
    """Handles generation for any OpenAI-compatible API, including local models."""
    client_params = {
        "api_key": os.environ.get("OPENAI_API_KEY")
    }
    # For local LLMs
    if model == 'local':
        client_params["base_url"] = "http://localhost:1234/v1"
        client_params["api_key"] = "not-needed"
        # The actual model name is often configured on the server side
        model = "local-model"

    client = openai.OpenAI(**client_params)

    # The OpenAI API pattern is to include the system prompt as the first message
    final_messages = messages
    if system_prompt:
        final_messages = [{"role": "developer", "content": system_prompt}] + messages

    response = client.chat.completions.create(
        model=model,
        messages=final_messages,  # CHANGED: Pass the full message list
        max_tokens=max_tokens,
        temperature=0.7
    )
    return response.choices[0].message.content.strip()


def _generate_with_claude(messages, system_prompt, model, max_tokens):
    """Handles generation for Anthropic's Claude models."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # The Anthropic API takes the system prompt as a separate top-level parameter
    response = client.messages.create(
        model=model,  # Use the model passed in
        system=system_prompt,  # NEW: Pass the system prompt here
        messages=messages,  # CHANGED: Pass the full message list
        max_tokens=max_tokens,
        temperature=0.3,
    )
    return response.content[0].text


def _generate_with_gemini(messages: list[dict], system_prompt: str, model: str, max_tokens: int):
    """
    Generates a response from Gemini using a multi-turn conversation history.

    Args:
        messages: A list of dicts, e.g. [{'role': 'user', 'content': 'Hi'}, {'role': 'model', 'content': 'Hello!'}]
        system_prompt: The system instruction for the model.
        model: The model name to use.
        max_tokens: The maximum number of tokens for the response.
    """
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    # Dynamically build the 'contents' list from the input 'messages'
    contents = []
    for message in messages:
        # The role in the SDK must be 'user' or 'model'
        role = message['role']
        if role == 'assistant':  # Common to see 'assistant', which maps to 'model'
            role = 'model'

        contents.append(types.Content(
            role=role,
            parts=[types.Part.from_text(text=message['content'])]
        ))
    #print(contents)
    # Configure the generation settings
    # Note: system_instruction in the latest versions expects a types.Content object or string
    generate_content_config = types.GenerateContentConfig(
        max_output_tokens=max_tokens,
        system_instruction=system_prompt,
        # temperature, top_p, etc. can also be set here
    )

    # Make the API call
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=generate_content_config,
    )

    # The response object contains a list of candidates, we usually want the first one.
    # The content of the candidate is a types.Content object.
    return response.candidates[0].content.parts[0].text



def generate_response(messages, system_prompt=None, model='claude-3-sonnet-20240229', max_tokens=20000):
    """
    Generates content using the specified LLM. Acts as a router to the correct provider.
    This function is now backward-compatible and can accept either a single string (for simple prompts)
    or a list of message dictionaries (for chat).
    """
    try:
        if 'gpt' in model or model == 'local':
            return _generate_with_openai(messages, system_prompt, model, max_tokens)
        elif 'claude' in model:
            # Pass the model name to the claude function
            return _generate_with_claude(messages, system_prompt, model, max_tokens)
        elif 'gemini' in model:
            return _generate_with_gemini(messages, system_prompt, model, max_tokens)
        else:
            raise ValueError(f"Unknown or unsupported model family: {model}")
    except Exception as e:
        logger.error(f"Error calling LLM API for model {model}: {e}")
        # Re-raise the exception to be handled by the Flask endpoint
        raise e

