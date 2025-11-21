from __future__ import annotations

import json
import os
from typing import Any, Dict, Callable

import openai
from agents import function_tool

# Import the Duffel functions (these should already be written and available)
from map_servers.duffel_server import (
    search_flights,
    # get_order,
    # create_order,
)

# ----------------------------------------------------------------------
# 1. Configure OpenAI LLM
# ----------------------------------------------------------------------

# OPTION A (recommended): read from environment variable
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError(
        "Please set OPENAI_API_KEY as an environment variable or "
        "hard-code it in agent_app.py before running."
    )

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

# ----------------------------------------------------------------------
# 2. Tool registry: names -> description + Python callables
# ----------------------------------------------------------------------

def _tool_schema() -> Dict[str, Dict[str, Any]]:
    """
    Describe tools in natural language + argument info.
    This is what the LLM sees when deciding which tool to call.
    """
    return {
        "search_flights": {
            "description": "Search for flight offers based on the provided origin, destination, and dates.",
            "args": {
                "origin": "string (required) - the IATA code for the origin airport (e.g., 'JFK').",
                "destination": "string (required) - the IATA code for the destination airport (e.g., 'LHR').",
                "departure_date": "string (required) - the departure date in YYYY-MM-DD format.",
                "return_date": "string (optional) - the return date for round-trip flights.",
                "passengers": "integer (optional) - the number of passengers (default is 1).",
                "cabin_class": "string (optional) - the cabin class (default is 'economy').",
                "max_offers": "integer (optional) - maximum number of flight offers to return (default is 5).",
            },
        },
        # "get_order": {
        #     "description": "Retrieve a flight order by its ID.",
        #     "args": {
        #         "order_id": "string (required) - the order ID (e.g., 'ord_abc123xyz')."
        #     },
        # },
        # "create_order": {
        #     "description": "Create a flight order from a selected offer.",
        #     "args": {
        #         "offer_id": "string (required) - the offer ID to create an order from.",
        #         "payment_type": "string (optional) - the payment type (default is 'balance').",
        #         "passengers": "array (optional) - list of passengers' details (if not provided, falls back to offer passengers).",
        #         "mode": "string (optional) - either 'instant' (pay now) or 'hold' (create a hold order).",
        #     },
        # },
    }

TOOL_FUNCTIONS: Dict[str, Callable[..., Any]] = {
    "search_flights": search_flights,
    # "get_order": get_order,
    # "create_order": create_order,
}

# ----------------------------------------------------------------------
# 3. Agent logic: decide tool vs direct answer, then explain
# ----------------------------------------------------------------------

def build_system_prompt() -> str:
    tools_desc = _tool_schema()
    tools_text_parts = []
    for name, spec in tools_desc.items():
        tools_text_parts.append(
            f"- {name}:\n"
            f"  description: {spec['description']}\n"
            f"  args: {json.dumps(spec['args'], indent=2)}"
        )
    tools_text = "\n".join(tools_text_parts)

    return (
        "You are a flight booking assistant that can call a set of tools (Duffel API functions).\n"
        "Tools available:\n"
        f"{tools_text}\n\n"
        "You MUST decide if you need to call a tool.\n"
        "If you need a tool, respond ONLY with a JSON object of the form:\n"
        '{\n'
        '  \"tool\": \"<tool_name>\",\n'
        '  \"args\": { ... }\n'
        '}\n'
        "where <tool_name> is one of the tools above, and args contains only simple JSON types.\n"
        "If you can answer directly without tools (e.g., conceptual explanation), respond ONLY with:\n"
        '{ \"answer\": \"<your natural language answer>\" }\n'
        "Do not add any extra text outside the JSON. The JSON must be the entire response."
    )

def ask_llm_for_tool_or_answer(user_message: str) -> Dict[str, Any]:
    """
    Step 1: ask the LLM whether to call a tool, and which one.

    Returns parsed JSON dict, either:
      { "answer": "..." }
    or
      { "tool": "<name>", "args": { ... } }
    """
    system_prompt = build_system_prompt()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    # Using openai.ChatCompletion.create instead of completions.create
    response = openai.completions.create(
        model="gpt-5",  # Update to an available model like gpt-3.5-turbo or gpt-4
        messages=messages,
        max_tokens=512,
    )

    # Extract response text
    text = response.choices[0].message["content"].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: wrap whatever the model said as a direct answer
        data = {"answer": text}

    return data

def ask_llm_to_explain_result(
    user_message: str,
    tool_name: str,
    args: Dict[str, Any],
    result: Any,
) -> str:
    """
    Step 3: after calling the tool, ask the LLM to explain the result.
    """
    tool_desc = _tool_schema().get(tool_name, {})
    prompt = (
        "You are a flight booking assistant. A tool has been called on behalf of the user.\n\n"
        f"User message:\n{user_message}\n\n"
        f"Tool used: {tool_name}\n"
        f"Tool description: {tool_desc.get('description', '')}\n"
        f"Arguments: {json.dumps(args, indent=2)}\n\n"
        f"Raw tool result (JSON):\n{json.dumps(result, indent=2)}\n\n"
        "Now explain the result to the user in clear natural language. "
        "Summarize key details of the flight offers, order status, or payment if applicable. "
        "Do not show the raw JSON, just a human-readable explanation."
    )

    messages = [
        {"role": "system", "content": "You are a helpful flight booking assistant."},
        {"role": "user", "content": prompt},
    ]

    response = openai.completions.create(
        model="gpt-5",  # Use a valid OpenAI model
        messages=messages,
        max_tokens=512,
    )

    return response.choices[0].message["content"].strip()


def handle_user_message(user_message: str) -> str:
    """
    Full agent flow for one user message:
    1. Ask LLM whether to use a tool or answer directly.
    2. If tool: run the Python function, then ask LLM to explain result.
    """
    decision = ask_llm_for_tool_or_answer(user_message)

    # Direct answer path
    if "answer" in decision and "tool" not in decision:
        return decision["answer"]

    # Tool path
    tool_name = decision.get("tool")
    args = decision.get("args", {}) or {}

    if tool_name not in TOOL_FUNCTIONS:
        return f"I tried to call an unknown tool '{tool_name}'. Please refine your request."

    tool_fn = TOOL_FUNCTIONS[tool_name]

    try:
        result = tool_fn(**args)
    except TypeError as e:
        return f"There was an error calling tool '{tool_name}' with arguments {args}: {e}"
    except Exception as e:
        return f"Tool '{tool_name}' failed with an exception: {e}"

    return ask_llm_to_explain_result(user_message, tool_name, args, result)


# ----------------------------------------------------------------------
# 4. Simple REPL
# ----------------------------------------------------------------------

def main() -> None:
    print(f"Flight Assistant (OpenAI model: gpt-3.5-turbo)")
    print("Type 'quit' or 'exit' to stop.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return

        if user_input.lower() in {"quit", "exit"}:
            print("Goodbye.")
            return

        if not user_input:
            continue

        answer = handle_user_message(user_input)
        print("\nAssistant:\n")
        print(answer)
        print("\n---\n")


if __name__ == "__main__":
    main()
