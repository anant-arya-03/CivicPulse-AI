import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from app.integrations.ai_providers.base import AIProviderError
from app.integrations.ai_providers.ollama_provider import OllamaProvider
from app.modules.ai import followup_template, letter_template
from app.modules.ai.agents import complaint_writer_agent, monitoring_agent, vision_agent
from app.modules.ai.image_prep import prepare_for_model
from app.modules.complaints.constants import CATEGORY_LABELS, Category

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../output/model-evaluation")
OUT.mkdir(parents=True, exist_ok=True)
if (OUT / "results.jsonl").exists():
    raise SystemExit("Choose a fresh output directory to preserve previous results.")
provider = OllamaProvider(model="gemma3:4b", timeout_seconds=180)


def scene(kind):
    image = Image.new("RGB", (640, 400), "#727275")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 640, 115), fill="#b2c6cd")
    draw.polygon([(0, 155), (640, 115), (640, 160), (0, 210)], fill="#c2b8a7")
    if kind == "pothole":
        draw.line((30, 330, 610, 230), fill="#e8c04f", width=7)
        draw.polygon(
            [(135, 250), (205, 220), (310, 226), (365, 254), (329, 281), (241, 294), (162, 278)],
            fill="#302923",
            outline="#b89c77",
            width=7,
        )
        for x in range(175, 335, 19):
            draw.ellipse((x, 251, x + 8, 257), fill="#857668")
    elif kind == "garbage":
        for x in (140, 275):
            draw.rectangle((x, 115, x + 110, 245), fill="#294d3a", outline="#102f21", width=4)
            draw.rectangle((x - 5, 105, x + 115, 121), fill="#1d3728")
        for x, y in [(120, 225), (350, 230), (395, 245), (279, 252), (445, 265)]:
            draw.polygon(
                [(x, y), (x + 23, y + 10), (x + 52, y + 32), (x + 42, y + 48), (x - 12, y + 43)],
                fill="#242429",
                outline="#54545b",
            )
        draw.rectangle((235, 265, 274, 290), fill="#bb824c")
        draw.ellipse((470, 300, 506, 313), fill="#cfddd2")
    elif kind == "drain":
        draw.polygon(
            [(90, 200), (600, 130), (600, 183), (90, 280)],
            fill="#3e4141",
            outline="#d1bb9f",
            width=8,
        )
        draw.polygon([(102, 250), (588, 164), (588, 179), (101, 272)], fill="#536d64")
    elif kind == "unrelated":
        draw.rectangle((0, 0, 640, 400), fill="#f1e5ce")
        draw.ellipse((180, 140, 440, 346), fill="#faf8f1", outline="#587488", width=12)
        draw.rounded_rectangle((252, 188, 370, 282), radius=15, fill="#654029")
        draw.ellipse((252, 176, 370, 218), fill="#b5815b")
        draw.arc((349, 202, 410, 255), 270, 90, fill="#654029", width=11)
    if kind == "ambiguous":
        draw.ellipse((305, 220, 348, 238), fill="#4c4c50")
        image = image.filter(ImageFilter.GaussianBlur(28))
    return image


photos = [
    ("V1", "../frontend/e2e/fixtures/pothole-sample.jpg", "ROAD_POTHOLE"),
    ("V2", "pothole", "ROAD_POTHOLE"),
    ("V3", "garbage", "GARBAGE_OVERFLOW"),
    ("V4", "drain", "OPEN_DRAIN"),
    ("V5", "unrelated", "OTHER"),
    ("V6", "ambiguous", "Express uncertainty and avoid unsupported claims"),
]

cases = [
    (
        Category.ROAD_POTHOLE,
        "Pothole near gate",
        "A pothole is visible beside the library gate.",
        "Library Road",
        None,
        1,
    ),
    (
        Category.GARBAGE_OVERFLOW,
        "Overflowing bins",
        "Waste is spilling from two bins onto the pavement.",
        "Market Lane",
        "20 November 2026, 09:00 UTC",
        2,
    ),
    (
        Category.BROKEN_STREETLIGHT,
        "Streetlight dark",
        "The lamp beside the bus stop was dark when I passed.",
        "Station Road",
        None,
        0,
    ),
]


def run(case_id, expected, inputs, invoke, baseline=None, render=None):
    row = {"id": case_id, "expected": expected, "input": inputs}
    if baseline:
        row["template"] = baseline
    try:
        result = invoke()
        row.update(
            model=result.model,
            latency_ms=result.latency_ms,
            output=result.output.model_dump(mode="json"),
        )
        if render:
            row["rendered_model"] = render(result.output)
    except AIProviderError as exc:
        row["error"] = {"code": exc.code, "message": str(exc)}
    with (OUT / "results.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(case_id, row.get("output", row.get("error")), flush=True)


for index, (category, title, description, street, observed, count) in enumerate(cases, 1):
    facts = dict(
        reference=f"CP-EVAL-{index:03}",
        title=title,
        category=category.value,
        category_label=CATEGORY_LABELS[category],
        severity_label="Not assessed",
        citizen_description=description,
        location_summary=f"{street}, Demo City",
        coordinates=None,
        observed_on=observed,
        photo_count=count,
        citizen_name=None,
    )
    run(
        f"L{index}",
        "Preserve supplied facts, make a relevant request and avoid unsupported claims",
        facts,
        lambda facts=facts: complaint_writer_agent.write_letter_prose(provider, facts),
        letter_template.render_letter(letter_template.template_prose(facts), facts),
        lambda prose, facts=facts: letter_template.render_letter(prose, facts),
    )

facts = dict(
    reminder_number=1,
    reference="CP-EVAL-004",
    department_reference=None,
    title="Pothole near gate",
    category_label=CATEGORY_LABELS[Category.ROAD_POTHOLE],
    location_summary="Library Road, Demo City",
    submitted_on="01 November 2026",
    previous_reminder_on=None,
    department_name="Demo Roads Department",
    listed_response_days=7,
    department_replied=False,
    citizen_name=None,
)
run(
    "R1",
    "Request an update without claiming a reply or acknowledgement",
    facts,
    lambda: monitoring_agent.write_followup_prose(provider, facts),
    followup_template.render_followup(followup_template.template_followup_prose(facts), facts),
    lambda prose: followup_template.render_followup(prose, facts),
)

for case_id, source, expected in photos:
    if source.endswith(".jpg"):
        path = Path(source)
    else:
        path = OUT / f"{case_id}-{source}.png"
        scene(source).save(path)
    image = prepare_for_model(path.read_bytes())
    run(
        case_id,
        expected,
        {"image": str(path), "synthetic": True},
        lambda image=image: vision_agent.analyze_photo(provider, image),
    )
