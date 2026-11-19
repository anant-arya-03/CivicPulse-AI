# CivicPulse department portal

Start the existing CivicPulse backend and frontend, then open <http://localhost:3000/department> in another tab. Use the citizen app in the first tab. Each tab keeps its own access mechanism, so opening the operator portal does not sign the citizen out.

1. In the repository-root `.env`, enable `ENABLE_SIMULATION` and set `DEPARTMENT_ACCESS_CODE` to a private random value of at least 24 characters. Keep it on the server. Restart the backend after changing these settings.
2. `DEPARTMENT_AUTHORITY_EMAIL` defaults to `roads@demo-city.example`, the fictional Demo City Roads and Infrastructure Department. Seed the demo directory with `python -m scripts.seed` from `backend/` if needed. Set the email to another active demo directory entry to demonstrate a different inbox.
3. Sign in to the portal with the access code. In the citizen app, send an approved pothole complaint to the configured demo department. The portal shows a new-report alert and displays the approved letter and submitted photos.
4. Open the report, choose **Start work**, then choose **Report repair complete**. The citizen detail page refreshes in the background and prompts the citizen to verify the repair.

The backend reads the same persisted simulated delivery record the citizen sees. The operator's structured updates enter the existing reply and status rules. The portal polls every three seconds while visible and the citizen detail refreshes every five seconds while visible. This is a local simulated inbox for one configured department. Attachment access is scoped to the evidence IDs in the approved delivery. The code stays in the operator tab's memory and refreshing the tab requires sign-in again.
