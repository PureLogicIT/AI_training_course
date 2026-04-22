"""
Exercise 2: Tokenizer Explorer
================================
A three-tab Gradio app for inspecting tokenization across multiple model families.

Tabs:
  1. Token Inspector     — visualise tokens as colored HTML badges
  2. Special Tokens      — display the special token table for a model family
  3. Chat Template       — show the formatted prompt after apply_chat_template()

Your job: implement all TODO sections.
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
# Step 2: HTML token badge renderer
# ---------------------------------------------------------------------------

def render_tokens_as_html(tokens: list, token_ids: list, special_ids: set) -> str:
    """
    Render tokens as colored HTML badges.

    - Special tokens (token_id in special_ids): orange background, white text.
    - Regular tokens: light blue background, dark text.
    - Spaces represented as "▁" or "Ġ" are replaced with "·" for readability.

    Args:
        tokens:      List of token strings (from convert_ids_to_tokens).
        token_ids:   Corresponding list of integer token IDs.
        special_ids: Set of special token IDs for this tokenizer.

    Returns:
        An HTML string ready to pass to gr.HTML.

    TODO:
      1. For each (token_text, token_id) pair in zip(tokens, token_ids):
           a. HTML-escape the token text using html.escape().
           b. Replace "▁" with "·" and "Ġ" with "·" for readability.
           c. Choose background color:
                - "#f97316" (orange) if token_id in special_ids
                - "#bfdbfe" (light blue) otherwise.
           d. Choose text color:
                - "white" if special token
                - "#1e3a5f" (dark blue) otherwise.
           e. Wrap in a <span> like:
                <span style="background:{bg}; color:{fg}; padding:2px 6px;
                             border-radius:4px; margin:2px; display:inline-block;
                             font-size:0.85em;">
                  {escaped_text}
                </span>
      2. Join all spans and wrap in:
           <div style="font-family: monospace; line-height: 3; padding: 8px;">
             ...spans...
           </div>
      3. Return the HTML string.
    """
    if not tokens:
        return "<p style='color: grey;'>No tokens to display.</p>"

    # TODO: implement HTML badge rendering
    raise NotImplementedError("render_tokens_as_html() is not implemented yet.")


# ---------------------------------------------------------------------------
# Tab 1 handler: Token Inspector
# ---------------------------------------------------------------------------

def inspect_tokens(text: str, model_family: str):
    """
    Tokenize the text for the given model family and return display values.

    Returns (html_str, ids_str, count) for the three Tab 1 outputs.

    TODO:
      1. Call tokenize_text(text, model_family) to get the info dict.
      2. Call render_tokens_as_html(info["tokens"], info["token_ids"], info["special_token_ids"]).
      3. Build ids_str = ", ".join(str(i) for i in info["token_ids"]).
      4. Return (html_str, ids_str, info["token_count"]).
    """
    if not text.strip():
        return "<p style='color: grey;'>Enter some text above.</p>", "", 0

    # TODO: implement inspect_tokens
    raise NotImplementedError("inspect_tokens() is not implemented yet.")


# ---------------------------------------------------------------------------
# Tab 2 handler: Special Tokens Reference
# ---------------------------------------------------------------------------

def load_special_tokens(model_family: str):
    """
    Load the tokenizer and return a list of rows for the special tokens table.

    Returns a list of [Token Name, Token String, Token ID] rows.

    TODO:
      1. Call get_tokenizer(model_family).
      2. Build rows for these named special tokens:
           - ("BOS", tokenizer.bos_token, tokenizer.bos_token_id)
           - ("EOS", tokenizer.eos_token, tokenizer.eos_token_id)
           - ("PAD", tokenizer.pad_token, tokenizer.pad_token_id)
           - ("UNK", tokenizer.unk_token, tokenizer.unk_token_id)
      3. For each additional special token in tokenizer.additional_special_tokens[:10]:
           token_id = tokenizer.convert_tokens_to_ids(token)
           row = ("Additional", token, token_id)
      4. Replace None values in token string column with "None".
      5. Replace None values in token ID column with "N/A".
      6. Return the list of rows.
    """
    # TODO: implement load_special_tokens
    raise NotImplementedError("load_special_tokens() is not implemented yet.")


# ---------------------------------------------------------------------------
# Tab 3 handler: Chat Template Preview
# ---------------------------------------------------------------------------

def preview_chat_template(user_text: str, model_family: str, include_system: bool) -> str:
    """
    Return the formatted chat template string for the given inputs.

    TODO:
      Call build_chat_template_preview(user_text, model_family, include_system)
      and return the result.
    """
    if not user_text.strip():
        return "Enter a message above."

    # TODO: implement preview_chat_template
    raise NotImplementedError("preview_chat_template() is not implemented yet.")


# ---------------------------------------------------------------------------
# Step 3: Gradio interface
# ---------------------------------------------------------------------------

def build_interface() -> gr.Blocks:
    """
    Build and return the three-tab Gradio Blocks interface.

    TODO:
      Tab 1 — Token Inspector:
        Inputs:  text_input (Textbox), family_tab1 (Dropdown)
        Button:  "Tokenize"
        Outputs: token_html (HTML), ids_output (Textbox), count_output (Number)
        Wire:    btn_tokenize.click -> inspect_tokens

      Tab 2 — Special Tokens Reference:
        Inputs:  family_tab2 (Dropdown)
        Button:  "Load Special Tokens"
        Output:  special_table (Dataframe, columns=["Token Name","Token String","Token ID"])
        Wire:    btn_special.click -> load_special_tokens

      Tab 3 — Chat Template Preview:
        Inputs:  msg_input (Textbox), family_tab3 (Dropdown), system_checkbox (Checkbox, default True)
        Button:  "Preview Template"
        Output:  template_output (Code, language="text")
        Wire:    btn_template.click -> preview_chat_template
    """
    with gr.Blocks(title="Tokenizer Explorer") as demo:
        gr.Markdown(
            "# Tokenizer Explorer\n"
            "Inspect tokenization, special tokens, and chat templates across model families.\n\n"
            "> Tokenizers download a few MB each (no model weights needed)."
        )

        with gr.Tabs():
            # ---------- Tab 1: Token Inspector ----------
            with gr.Tab("Token Inspector"):
                gr.Markdown("Encode text and see each token as a colored badge.")

                # TODO: add Tab 1 components and wire them

                pass  # Remove when implementing

            # ---------- Tab 2: Special Tokens ----------
            with gr.Tab("Special Tokens Reference"):
                gr.Markdown("View BOS, EOS, PAD, UNK, and additional special tokens for each model family.")

                # TODO: add Tab 2 components and wire them

                pass  # Remove when implementing

            # ---------- Tab 3: Chat Template ----------
            with gr.Tab("Chat Template Preview"):
                gr.Markdown(
                    "See what your message looks like after `apply_chat_template()` — "
                    "the exact format the model was trained on."
                )

                # TODO: add Tab 3 components and wire them

                pass  # Remove when implementing

    return demo


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo = build_interface()
    demo.launch(server_name="0.0.0.0", server_port=7860)
