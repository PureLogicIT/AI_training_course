"""
Exercise 3 — Multi-Turn Model Comparison App (SOLUTION)
"""

from __future__ import annotations

import os
from typing import Generator

import gradio as gr
import ollama

from conversation import ConversationManager
from inference import stream_response, compare_responses

# ---------------------------------------------------------------------------
# Shared Ollama client
# ---------------------------------------------------------------------------

OLLAMA_HOST: str = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
client: ollama.Client = ollama.Client(host=OLLAMA_HOST)

SYSTEM_PROMPT = (
    "You are a helpful and knowledgeable assistant. "
    "Answer clearly and concisely."
)

DEFAULT_OPTIONS: dict = {"temperature": 0.7, "num_ctx": 4096}

COMPARE_SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer clearly and concisely."
)


def get_models() -> list[str]:
    try:
        return [m.model for m in client.list().models]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Tab 1 — Chat
# ---------------------------------------------------------------------------

def send_message(
    user_text: str,
    model: str,
    conv_manager: ConversationManager,
) -> Generator[tuple, None, None]:
    """Stream a response and yield Gradio updates incrementally."""
    if not user_text.strip():
        yield (conv_manager.to_gradio_history(), "", conv_manager)
        return

    conv_manager.add_user(user_text)

    partial: list[str] = []
    stats_text: str = "Generating…"

    # Show the user message immediately with an empty assistant slot
    streaming_history = conv_manager.to_gradio_history()
    # The last pair has assistant=None; replace with empty string for display
    if streaming_history and streaming_history[-1][1] is None:
        streaming_history[-1][1] = ""

    yield (streaming_history, stats_text, conv_manager)

    for item in stream_response(client, model, conv_manager.get_ollama_messages(), DEFAULT_OPTIONS):
        if isinstance(item, dict) and item.get("done"):
            # Final sentinel — commit assistant turn and build stats
            full_reply = "".join(partial)
            conv_manager.add_assistant(full_reply, model_name=model)
            s = item["stats"]
            stats_text = (
                f"**{s['total_tokens']} tokens** | "
                f"**{s['tokens_per_sec']:.1f} tok/s** | "
                f"model: `{model}`"
            )
            yield (conv_manager.to_gradio_history(), stats_text, conv_manager)
        else:
            # Token chunk
            token: str = item  # type: ignore[assignment]
            partial.append(token)
            # Update the last assistant slot with accumulated text
            live_history = conv_manager.to_gradio_history()
            if live_history and live_history[-1][1] is None:
                live_history[-1] = [live_history[-1][0], "".join(partial)]
            elif live_history:
                live_history.append([None, "".join(partial)])
            yield (live_history, stats_text, conv_manager)


# ---------------------------------------------------------------------------
# Tab 1 — Model switching
# ---------------------------------------------------------------------------

def switch_model(
    new_model: str,
    conv_manager: ConversationManager,
) -> tuple[list[list], ConversationManager]:
    if new_model and conv_manager.turn_count > 0:
        conv_manager.add_assistant(
            f"[Switched to model: {new_model}]",
            model_name=new_model,
        )
    return conv_manager.to_gradio_history(), conv_manager


# ---------------------------------------------------------------------------
# Tab 2 — Save / Load
# ---------------------------------------------------------------------------

def save_conversation(filepath: str, conv_manager: ConversationManager) -> str:
    if not filepath.strip():
        return "Please enter a file path."
    try:
        conv_manager.save_to_json(filepath.strip())
        return f"Conversation saved to `{filepath.strip()}`."
    except IOError as exc:
        return f"Save failed: {exc}"


def load_conversation(
    file_obj,
    conv_manager: ConversationManager,
) -> tuple[list[list], ConversationManager, str]:
    if file_obj is None:
        return conv_manager.to_gradio_history(), conv_manager, "No file selected."
    try:
        conv_manager.load_from_json(file_obj.name)
        turns = conv_manager.turn_count
        return (
            conv_manager.to_gradio_history(),
            conv_manager,
            f"Loaded {turns} turn(s) from `{file_obj.name}`.",
        )
    except (ValueError, IOError) as exc:
        return conv_manager.to_gradio_history(), conv_manager, f"Load failed: {exc}"


# ---------------------------------------------------------------------------
# Tab 3 — Compare
# ---------------------------------------------------------------------------

def run_compare(
    prompt: str,
    model_a: str,
    model_b: str,
) -> tuple[str, str, str, str]:
    if not prompt.strip():
        return "Please enter a prompt.", "", "", ""
    if not model_a or not model_b:
        return "Please select both models.", "", "", ""

    messages = [
        {"role": "system", "content": COMPARE_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    (text_a, stats_a), (text_b, stats_b) = compare_responses(
        client, model_a, model_b, messages, DEFAULT_OPTIONS
    )

    def fmt_stats(model: str, stats: dict) -> str:
        return (
            f"**{model}** — "
            f"{stats['total_tokens']} tokens | "
            f"{stats['tokens_per_sec']:.1f} tok/s"
        )

    return text_a, text_b, fmt_stats(model_a, stats_a), fmt_stats(model_b, stats_b)


# ---------------------------------------------------------------------------
# Full UI
# ---------------------------------------------------------------------------

def build_ui() -> gr.Blocks:
    models = get_models()
    default_model = models[0] if models else ""

    with gr.Blocks(title="Multi-Model Chat") as demo:
        gr.Markdown("# Multi-Turn Model Comparison App")

        conv_state = gr.State(lambda: ConversationManager(system_prompt=SYSTEM_PROMPT))

        with gr.Tabs():

            # ----------------------------------------------------------------
            # Tab 1 — Chat
            # ----------------------------------------------------------------
            with gr.Tab("Chat"):
                model_dd = gr.Dropdown(
                    choices=models,
                    value=default_model,
                    label="Model",
                )

                chatbot = gr.Chatbot(height=480, label="Conversation")

                stats_display = gr.Markdown(
                    value="*Stats will appear after the first response.*"
                )

                with gr.Row():
                    msg_box = gr.Textbox(
                        placeholder="Type a message and press Enter…",
                        label="Your message",
                        scale=8,
                        show_label=False,
                    )
                    send_btn = gr.Button("Send", variant="primary", scale=1)

                def _submit(text, model, state):
                    yield from send_message(text, model, state)

                msg_box.submit(
                    fn=_submit,
                    inputs=[msg_box, model_dd, conv_state],
                    outputs=[chatbot, stats_display, conv_state],
                )
                send_btn.click(
                    fn=_submit,
                    inputs=[msg_box, model_dd, conv_state],
                    outputs=[chatbot, stats_display, conv_state],
                )

                model_dd.change(
                    fn=switch_model,
                    inputs=[model_dd, conv_state],
                    outputs=[chatbot, conv_state],
                )

            # ----------------------------------------------------------------
            # Tab 2 — Save / Load
            # ----------------------------------------------------------------
            with gr.Tab("Save / Load"):
                gr.Markdown("### Save conversation to JSON")
                with gr.Row():
                    save_path_box = gr.Textbox(
                        value="conversation.json",
                        label="Save path",
                        scale=4,
                    )
                    save_btn = gr.Button("Save", scale=1)
                save_status = gr.Markdown()

                save_btn.click(
                    fn=save_conversation,
                    inputs=[save_path_box, conv_state],
                    outputs=[save_status],
                )

                gr.Markdown("### Load conversation from JSON")
                load_file = gr.File(label="Upload .json file", file_types=[".json"])
                load_btn = gr.Button("Load")
                load_status = gr.Markdown()

                load_btn.click(
                    fn=load_conversation,
                    inputs=[load_file, conv_state],
                    outputs=[chatbot, conv_state, load_status],
                )

            # ----------------------------------------------------------------
            # Tab 3 — Compare
            # ----------------------------------------------------------------
            with gr.Tab("Compare"):
                gr.Markdown(
                    "Send the same prompt to two models simultaneously "
                    "and compare responses side by side."
                )
                with gr.Row():
                    compare_model_a = gr.Dropdown(
                        choices=models,
                        value=models[0] if len(models) > 0 else None,
                        label="Model A",
                    )
                    compare_model_b = gr.Dropdown(
                        choices=models,
                        value=models[1] if len(models) > 1 else (models[0] if models else None),
                        label="Model B",
                    )

                compare_prompt = gr.Textbox(
                    label="Prompt",
                    lines=3,
                    placeholder="Enter a prompt to send to both models…",
                )
                compare_btn = gr.Button("Compare", variant="primary")

                with gr.Row():
                    output_a = gr.Textbox(
                        label="Model A Response",
                        lines=12,
                        interactive=False,
                        scale=1,
                    )
                    output_b = gr.Textbox(
                        label="Model B Response",
                        lines=12,
                        interactive=False,
                        scale=1,
                    )

                with gr.Row():
                    stats_a = gr.Markdown()
                    stats_b = gr.Markdown()

                compare_btn.click(
                    fn=run_compare,
                    inputs=[compare_prompt, compare_model_a, compare_model_b],
                    outputs=[output_a, output_b, stats_a, stats_b],
                )

    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.launch(server_name="0.0.0.0", server_port=7860)
