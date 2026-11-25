# CivicPulse AI model evaluation

Local run on 25 November 2026 using Ollama 0.40.18 and Gemma 3 4B (`gemma3:4b`, Q4_K_M) on a laptop with an NVIDIA RTX 3050 Laptop GPU (4 GiB VRAM). The runner called the app's backend agents and image preparation directly, using `vision.v1`, `complaint_letter.v1` and `followup_letter.v1` with the app's output schemas and temperature 0. Each case had one attempt and a 180-second provider timeout. Input labels and expected behavior were set before inference. The writing cases use fictional report facts and the six vision cases use synthetic illustrations, including the repository's pothole fixture.

The [case records](results.jsonl) contain inputs, validated model responses or provider errors, provider latency, and complete rendered model and template drafts for the writing cases. Scoring was a single-reviewer check. A photo passes when its category matches the label, or when the ambiguous image elicits genuine uncertainty without invented details. A letter passes when it preserves the supplied facts and requests an action that directly addresses the reported issue. Potential risks framed as possibilities were allowed. The reminder passes when it requests an update without implying an earlier reply or acknowledgement.

## Vision cases

| Case | Input | Expected | Observed |
|---|---|---|---|
| V1 | Repository pothole illustration | `ROAD_POTHOLE` | `ROAD_POTHOLE` |
| V2 | Road with a pothole beside a yellow line | `ROAD_POTHOLE` | `ROAD_POTHOLE` |
| V3 | Two bins with scattered waste | `GARBAGE_OVERFLOW` | `GARBAGE_OVERFLOW` |
| V4 | Uncovered roadside channel | `OPEN_DRAIN` | `OPEN_DRAIN` |
| V5 | Cup illustration | `OTHER` | `OTHER` |
| V6 | Blurred colour road illustration with an indistinct mark | Express uncertainty and avoid unsupported descriptions | Said it was impossible to determine whether there was a civic issue. Also called it a grayscale photograph and returned `HIGH` confidence. |

Vision passed 5 of 6 checks. The five cases with category labels all matched. V6 failed the full ambiguity check because of the inaccurate grayscale description, despite acknowledging uncertainty in the prose. These scores reflect the stated criteria for each case. They do not measure real-world photo accuracy.

## Complaint letters and template comparison

| Case | Gemma | Existing template |
|---|---|---|
| L1 · Pothole | Pass. Requests inspection and repair. Adds no date or duration. | Pass. Requests inspection and repair of the damaged surface. |
| L2 · Overflowing bins | Fail on requested action. Keeps the supplied facts. Asks about bin capacity and omits clearing the waste already on the pavement. | Pass. Explicitly asks for waste clearance and for the bins to be emptied. |
| L3 · Dark streetlight | Pass. Requests inspection and repair. Adds no date or duration. | Pass. Requests inspection and repair or replacement. |

All three model letters preserved the supplied facts. Gemma passed the combined facts-and-action check on 2 of 3 cases and the template passed 3 of 3. The same backend renderer supplies the structured details for both. Gemma also tailored its wording to the report, for example by referring to pedestrians using the bus stop in L3. This run did not measure reader preference.

## Failure analysis

L2's input said, “Waste is spilling from two bins onto the pavement.” Gemma asked for action “to ensure they are adequately sized for the volume of waste generated.” The template asked to “arrange for the waste to be cleared and the bins emptied.” Gemma's draft passed the output schema and still needed an edit to make the requested action address the immediate problem.

V2 also shows why a correct label can coexist with a misleading description. Gemma correctly identified a pothole and said a yellow line surrounded it. The [input image](V2-pothole.png) shows a straight road line running alongside the pothole.

## Reminder regression check

R1 passed. The input set `department_replied` to `false`. Gemma asked for the status and expected date of action without claiming an acknowledgement. The template explicitly stated that no reply had been received. This reproduces the earlier failure condition with a new fictional complaint.

## Presentation slide copy

**Gemma 3 4B passed 8 of 10 controlled checks**

- **Vision 5/6.** All five category labels matched. The blurred colour illustration was described as grayscale.
- **Complaint letters 2/3.** All three kept the supplied facts. One omitted the immediate cleanup request. The template passed 3/3 on the same inputs.
- **Reminder 1/1.** Asked for an update without implying an earlier reply.
- **Schema validation 10/10.** Valid structure still left an action for the citizen to correct.

*One local run using synthetic illustrations and fictional report facts.*

## Reproduce locally

From the repository root in PowerShell, with Ollama running and `gemma3:4b` installed:

```powershell
Set-Location backend
$env:PYTHONPATH = (Get-Location).Path
.venv/Scripts/python.exe ../output/model-evaluation/run.py ../output/model-evaluation-rerun
```

Choose a fresh output directory for each run. The runner writes the first response or error for each case as soon as it completes. It does not open a database session or send emails.
