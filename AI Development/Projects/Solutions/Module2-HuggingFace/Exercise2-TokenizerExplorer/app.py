"""
Exercise 2: Tokenizer Explorer — SOLUTION
==========================================
A three-tab Gradio app for inspecting tokenization across multiple model families.
"""

import html
import gradio as gr
from tokenizer_utils import (
    FAMILY_TO_MODEL,
    get_tokenizer,
    tokenize_text,
    build_chat_template_preview,
)

FAMILY_CHOICES = list(FAMILY_TO_MODEL.keys())


# ---------------------------------------------------------------------------
# HTML token badge renderer
# ---------------------------------------------------------------------------

def render_tokens_as_html(tokens: list, token_ids: list, special_ids: set) -> str:
    """Render tokens as colored HTML badge spans."""
    if not tokens:
        return "<p style='color: grey;'>No tokens to display.</p>"

    spans = []
    for token_text, token_id in zip(tokens, token_ids):
        # HTML-escape and make spaces readable
        escaped = html.escape(str(token_text))
        escaped = escaped.replace("▁", "·").replace("Ġ", "·")

        is_special = token_id in special_ids
        bg = "#f97316" if is_special else "#bfdbfe"
        fg = "white" if is_special else "#1e3a5f"

        span = (
            f'<span style="background:{bg}; color:{fg}; padding:2px 6px; '
            f'border-radius:4px; margin:2px; display:inline-block; '
            f'font-size:0.85em;" title="ID: {token_id}">'
            f'{escaped}</span>'
        )
        spans.append(span)

    inner = "\n".join(spans)
    return (
        f'<div style="font-family: monospace; line-height: 3; padding: 8px; '
        f'background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;">'
        f'{inner}</div>'
    )


# ---------------------------------------------------------------------------
# Tab 1: Token Inspector
# ---------------------------------------------------------------------------

def inspect_tokens(text: str, model_family: str):
    """Tokenize text and return (html, ids_str, count) for Tab 1 outputs."""
    if not text.strip():
        return "<p style='color: grey;'>Enter some text above.</p>", "", 0

    info = tokenize_text(text, model_family)
    html_str = render_tokens_as_html(
        info["tokens"], info["token_ids"], info["special_token_ids"]
    )
    ids_str = ", ".join(str(i) for i in info["token_ids"])
    return html_str, ids_str, info["token_count"]


# ---------------------------------------------------------------------------
# Tab 2: Special Tokens Reference
# ---------------------------------------------------------------------------

def load_special_tokens(model_family: str):
    """Return a list of [Name, Token String, Token ID] rows for the special tokens table."""
    tokenizer = get_tokenizer(model_family)

    named = [
        ("BOS", tokenizer.bos_token, tokenizer.bos_token_id),
        ("EOS", tokenizer.eos_token, tokenizer.eos_token_id),
        ("PAD", tokenizer.pad_token, tokenizer.pad_token_id),
        ("UNK", tokenizer.unk_token, tokenizer.unk_token_id),
    ]

    rows = []
    for name, tok_str, tok_id in named:
        rows.append([name, tok_str if tok_str is not None else "None",
                     tok_id if tok_id is not None else "N/A"])

    for tok in tokenizer.additional_special_tokens[:10]:
        tok_id = tokenizer.convert_tokens_to_ids(tok)
        rows.append(["Additional", tok, tok_id])

    return rows


# ---------------------------------------------------------------------------
# Tab 3: Chat Template Preview
# ---------------------------------------------------------------------------

def preview_chat_template(user_text: str, model_family: str, include_system: bool) -> str:
    """Return the chat-template-formatted prompt string."""
    if not user_text.strip():
        return "Enter a message above."
    return build_chat_template_preview(user_text, model_family, include_system)


# ---------------------------------------------------------------------------
# Gradio interface
# ---------------------------------------------------------------------------

def build_interface() -> gr.Blocks:
    """Build and return the three-tab Gradio Blocks interface."""
    with gr.Blocks(title="Tokenizer Explorer") as demo:
        gr.Markdown(
            "# Tokenizer Explorer\n"
            "Inspect tokenization, special tokens, and chat templates across model families.\n\n"
            "> Tokenizers are a few MB each — no full model weights are downloaded."
        )

        with gr.Tabs():

            # ----------------------------------------------------------------
            # Tab 1: Token Inspector
            # ----------------------------------------------------------------
            with gr.Tab("Token Inspector"):
                gr.Markdown("Encode text and see each token as a colored badge.")

                with gr.Row():
                    text_input = gr.Textbox(
                        label="Input Text",
                        placeholder="Enter any text to tokenize...",
                        lines=4,
                    )
                    family_tab1 = gr.Dropdown(
                        choices=FAMILY_CHOICES,
                        value="smollm2",
                        label="Model Family",
                    )

                btn_tokenize = gr.Button("Tokenize", variant="primary")

                token_html = gr.HTML(label="Token Visualization")

                with gr.Row():
                    ids_output = gr.Textbox(
                        label="Token IDs",
                        interactive=False,
                        lines=3,
                    )
                    count_output = gr.Number(
                        label="Token Count",
                        interactive=False,
                    )

                btn_tokenize.click(
                    fn=inspect_tokens,
                    inputs=[text_input, family_tab1],
                    outputs=[token_html, ids_output, count_output],
                )

            # ----------------------------------------------------------------
            # Tab 2: Special Tokens Reference
            # ----------------------------------------------------------------
            with gr.Tab("Special Tokens Reference"):
                gr.Markdown(
                    "View BOS, EOS, PAD, UNK, and additional special tokens for each model family."
                )

                family_tab2 = gr.Dropdown(
                    choices=FAMILY_CHOICES,
                    value="smollm2",
                    label="Model Family",
                )
                btn_special = gr.Button("Load Special Tokens", variant="primary")
                special_table = gr.Dataframe(
                    headers=["Token Name", "Token String", "Token ID"],
                    label="Special Tokens",
                    interactive=False,
                )

                btn_special.click(
                    fn=load_special_tokens,
                    inputs=[family_tab2],
                    outputs=[special_table],
                )

            # ----------------------------------------------------------------
            # Tab 3: Chat Template Preview
            # ----------------------------------------------------------------
            with gr.Tab("Chat Template Preview"):
                gr.Markdown(
                    "See what your message looks like after `apply_chat_template()` — "
                    "the exact bytes the model was trained on."
                )

                with gr.Row():
                    msg_input = gr.Textbox(
                        label="User Message",
                        placeholder="e.g. What is a transformer model?",
                        lines=3,
                    )
                    with gr.Column():
                        family_tab3 = gr.Dropdown(
                            choices=FAMILY_CHOICES,
                            value="smollm2",
                            label="Model Family",
                        )
                        system_checkbox = gr.Checkbox(
                            label="Include system prompt",
                            value=True,
                        )

                btn_template = gr.Button("Preview Template", variant="primary")
                template_output = gr.Code(
                    label="Formatted Prompt (raw string)",
                    language="text",
                    interactive=False,
                )

                btn_template.click(
                    fn=preview_chat_template,
                    inputs=[msg_input, family_tab3, system_checkbox],
                    outputs=[template_output],
                )

    return demo


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo = build_interface()
    demo.launch(server_name="0.0.0.0", server_port=7860)
