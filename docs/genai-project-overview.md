# CivicPulse AI

**Generative AI project overview · Civic infrastructure reporting**

## Use case

A citizen notices a pothole, broken streetlight, or overflowing bin and wants the responsible department to take action. They may have a photo but still need to describe the issue, write a formal complaint, and follow up. CivicPulse helps the citizen go from a photo and confirmed details to an editable complaint, then track the response and verify the repair.

The classroom demo uses fictional departments and simulated delivery. A local department portal lets a teammate play the role of a department operator and show how work updates reach the citizen.

## What generative AI contributes

CivicPulse uses **Gemma 3 4B**, a pretrained multimodal model running locally through Ollama. The project uses task-specific prompts and structured outputs to turn images and confirmed facts into editable suggestions and drafts. It uses the pretrained model as supplied.

| Task | Input | Output and use |
|---|---|---|
| Photo analysis | One image of the reported issue | Suggested category, title, description, and severity for the citizen to review |
| Complaint writing | Confirmed issue details and location | A subject, issue summary, and requested action. The application inserts structured facts such as the reference and location into the letter. |
| Reply monitoring and reminders | Department reply text or confirmed follow-up facts | A suggested meaning for the reply or wording for a reminder. Backend rules determine status changes and when a reminder is due. |
| Repair check | Before and after photos | Advice on whether the issue appears fixed. The citizen makes the final decision. |

## How the project works

1. **Report the issue.** The citizen uploads a pothole photo. The application validates the image, strips embedded metadata, and asks Gemma for suggestions. The citizen confirms, edits, or enters the details manually.
2. **Confirm the location and department.** The citizen enters the address. The backend matches the issue and location against directory records. In simulation mode, the citizen can explicitly select a fictional demo department if there is no geographic match.
3. **Generate and review the letter.** Gemma drafts wording from the confirmed facts. The citizen can edit the result or use the built-in template. The citizen approves the exact message before simulated delivery. Any edit requires fresh approval.
4. **Track the complaint.** The local department portal can show the approved report and photos to a demo operator. The operator can mark work started or report a repair complete. The citizen sees the progress in the complaint timeline. If a reply is overdue, the worker can prepare a reminder draft for the citizen to review and approve.
5. **Verify the repair.** The citizen can upload an after photo and ask Gemma to compare it with the original. The citizen can confirm the repair or reopen the complaint. Manual verification is also available.

## Example and evaluation

For an overflowing-bin report, the model needs to turn the citizen’s observation into a useful request. In one test, Gemma kept the fact that waste had spilled onto the pavement but asked the department to assess bin capacity. The template explicitly asked the department to clear the waste and empty the bins. Gemma’s output passed schema validation and still missed the immediate cleanup request. That’s why the citizen reviews the wording before approving it.

Gemma passed **8 of 10 task checks** and **10 of 10 schema checks** in a controlled run. It passed 5 of 6 vision checks, 2 of 3 complaint-letter checks, and the no-reply reminder check. The template passed all three complaint-letter checks on the same inputs. The run used synthetic illustrations and fictional complaint facts. [Evaluation cases and model outputs](../output/model-evaluation/README.md)

## Project materials

- [CivicPulse AI on GitHub](https://github.com/anant-arya-03/CivicPulse-AI)
- [High-level design, architecture, and tech stack](genai-demo-design.md)
- [Setup and showcase walkthrough](../README.md)
- [Local department portal demo](../department/README.md)
