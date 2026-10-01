"""
ai_chat_sidebar_deepseek.py

Shared, collapsible right-hand AI chat panel, importable from every page.
Backed by DeepSeek's API, which is OpenAI-compatible, so this uses the
`openai` Python SDK pointed at DeepSeek's base_url instead of OpenAI's.

SETUP: put your DeepSeek key in .streamlit/secrets.toml (create this file,
it should NOT be committed to git):

    DEEPSEEK_API_KEY = "sk-your-key-here"
"""

import json
import streamlit as st
from openai import OpenAI

MODEL_NAME = "deepseek-flash"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def _get_client():
    api_key = st.secrets.get("DEEPSEEK_API_KEY", None) if hasattr(st, "secrets") else None
    if not api_key:
        raise RuntimeError(
            "No DEEPSEEK_API_KEY found. Add it to .streamlit/secrets.toml as:\n"
            'DEEPSEEK_API_KEY = "sk-your-key-here"'
        )
    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


def _run_agent_turn(user_message: str, tools: list, tool_functions: dict, system_prompt: str):
    client = _get_client()

    if not st.session_state.chat_messages:
        st.session_state.chat_messages.append({"role": "system", "content": system_prompt})

    st.session_state.chat_messages.append({"role": "user", "content": user_message})

    while True:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=st.session_state.chat_messages,
            tools=tools if tools else None,
        )
        message = response.choices[0].message

        assistant_entry = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in message.tool_calls
            ]
        st.session_state.chat_messages.append(assistant_entry)

        if message.tool_calls:
            for tc in message.tool_calls:
                func = tool_functions.get(tc.function.name)
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {}
                result = func(**args) if func else {"error": f"Unknown tool {tc.function.name}"}
                st.session_state.chat_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(result),
                })
            continue

        return message.content or ""


def render_chat_sidebar(tools=None, tool_functions=None, system_prompt=None):
    tools = tools or []
    tool_functions = tool_functions or {}
    system_prompt = system_prompt or (
        "You are a helpful assistant embedded in a supply chain analytics dashboard. "
        "Use the available tools to look up real data before answering questions about "
        "the graph, centrality scores, or supply chain metrics. Keep answers concise."
    )

    if "chat_open" not in st.session_state:
        st.session_state.chat_open = True
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    toggle_label = "💬 Hide AI Chat" if st.session_state.chat_open else "💬 Show AI Chat"
    if st.button(toggle_label, key="chat_toggle_btn"):
        st.session_state.chat_open = not st.session_state.chat_open
        st.rerun()

    if st.session_state.chat_open:
        main_col, chat_col = st.columns([3, 1])
    else:
        main_col, chat_col = st.columns([1, 0.0001])

    if st.session_state.chat_open:
        with chat_col:
            st.markdown("#### 🤖 AI Chat")
            chat_box = st.container(height=450)
            with chat_box:
                for msg in st.session_state.chat_messages:
                    if msg["role"] == "user":
                        with st.chat_message("user"):
                            st.write(msg["content"])
                    elif msg["role"] == "assistant" and msg.get("content"):
                        with st.chat_message("assistant"):
                            st.write(msg["content"])

            user_input = st.chat_input("Ask about this data...", key="chat_input_box")
            if user_input:
                try:
                    with st.spinner("Thinking..."):
                        _run_agent_turn(user_input, tools, tool_functions, system_prompt)
                    st.rerun()
                except Exception as e:
                    st.error(f"Chat error: {e}")
                    st.exception(e)

            if st.button("Clear chat", key="clear_chat_btn"):
                st.session_state.chat_messages = []
                st.rerun()

    return main_col, chat_col