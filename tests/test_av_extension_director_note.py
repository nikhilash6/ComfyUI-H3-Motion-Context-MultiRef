import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "example_workflows" / "NEW - AV Extension.json"


def _workflow():
    return json.loads(WORKFLOW.read_text(encoding="utf-8"))


def test_av_extension_includes_prompt_director_note_above_workflow():
    data = _workflow()
    director = [
        node for node in data["nodes"]
        if node.get("type") == "Note"
        and node.get("widgets_values_named", {}).get("text", "").startswith(
            "# MINIMAX H3 AV EXTENSION — PROMPT DIRECTOR"
        )
    ]
    assert len(director) == 1
    note = director[0]
    text = note["widgets_values_named"]["text"]
    assert "Your job is to take a user's rough concept" in text
    assert "# REQUIRED USER INFORMATION" in text
    assert "# WORKFLOW CONTINUATION MODEL" in text
    assert "# COPY-PASTE BOX REQUIREMENT" in text
    assert "Here is the user's AV Extension request:" in text
    other_y = [node["pos"][1] for node in data["nodes"] if node["id"] != note["id"]]
    assert note["pos"][1] < min(other_y)


def test_av_extension_note_does_not_tell_users_to_enable_extensions_manually_in_order():
    data = _workflow()
    notes = "\n".join(
        node.get("widgets_values_named", {}).get("text", "")
        for node in data["nodes"]
        if node.get("type") == "Note"
    )
    assert "Enable extensions in order." not in notes
    assert "controller enables/bypasses managed extension groups from Active Extensions" in notes
