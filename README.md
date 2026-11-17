# HOLLOWNET - Patriot HackFest Fall 2026 (Life Underground)
Run: python3 server.py   then open http://localhost:8000   (Python 3.8+, nothing to install)

Files: server.py (simulation + API), index.html (dashboard).
A simulated Hollow (10 levels x 5 neighborhoods) updates every 2s; every module reads the same shared state.

Modules -> problems: Early Warning (1), Fair Share (2), Cooling (3), Water Watch (4), Tunnel Safety + BFS routing (5),
Space Exchange (6), Mesh Chat (7), Family Check-In (8), Outbreak + Dispatch (9), Tele-Clinic (10), Wellness (11),
Farm (12), Surface Ledger hash chain (13), Ascent Planner (14), Migration Sim (15).

Demo flow: Overview map -> turn Directorate network OFF -> send a mesh message -> family check-in ->
Outbreak "real vs official" -> Surface tab: tamper with the ledger and watch the chain break.

Run the tests: python test_hollownet.py  (26 checks: input abuse + 3000-tick simulation stress test)
Open in browser: http://localhost:8000 (server only listens on your own computer by default)

Echo chatbot: click the robot at the bottom-right. Works offline out of the box.
For real AI answers (optional): set ANTHROPIC_API_KEY before starting.
  Windows PowerShell:  $env:ANTHROPIC_API_KEY="your-key"; python server.py
  Mac/Linux:           ANTHROPIC_API_KEY=your-key python3 server.py
