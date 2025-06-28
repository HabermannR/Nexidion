import os
import openai
import anthropic
import logging

logger = logging.getLogger(__name__)



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


# --- Main Interface and Logging (UPDATED) ---

def generate_response(prompt_or_messages, system_prompt=None, model='claude-3-sonnet-20240229', max_tokens=20000):
    """
    Generates content using the specified LLM. Acts as a router to the correct provider.
    This function is now backward-compatible and can accept either a single string (for simple prompts)
    or a list of message dictionaries (for chat).
    """
    # KEY IMPROVEMENT: Handle both old and new input types
    if isinstance(prompt_or_messages, str):
        # This is the old way (e.g., "Generate content for this node")
        messages = [{"role": "user", "content": prompt_or_messages}]
        # The prompt string itself now serves as the "messages"
    elif isinstance(prompt_or_messages, list):
        # This is the new way (for chat)
        messages = prompt_or_messages
    else:
        raise TypeError("prompt_or_messages must be a string or a list of message dicts")

    try:
        if 'gpt' in model or model == 'local':
            response = _generate_with_openai(messages, system_prompt, model, max_tokens)
        elif 'claude' in model:
            # Pass the model name to the claude function
            response = _generate_with_claude(messages, system_prompt, model, max_tokens)
        else:
            raise ValueError(f"Unknown or unsupported model family: {model}")

        return response
    except Exception as e:
        logger.error(f"Error calling LLM API for model {model}: {e}")
        # Re-raise the exception to be handled by the Flask endpoint
        raise e

