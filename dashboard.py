#dashboard.py
#!/usr/bin/env python3
"""
Pi-Patrol Dashboard (Front-end)
Flask-based monitoring dashboard with live preview + event log + enroll option + control toggle.
"""

from flask import Flask, jsonify, send_from_directory, request
import sqlite3
from pathlib import Path
import requests

app = Flask(_name_)

BASE_DIR = Path("/home/pi/Security/pi_patrol")
DB_PATH = BASE_DIR / "patrol.db"
EVENTS_DIR = BASE_DIR / "events"
RECORDINGS_DIR = BASE_DIR / "recordings"

WEB_API_BASE = "http://localhost:5050"
ENROLL_API = f"{WEB_API_BASE}/api/enroll"
TOGGLE_API = f"{WEB_API_BASE}/api/toggle_preview"
STATUS_API = f"{WEB_API_BASE}/api/status"


# ========== Helper ==========
def get_events():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, timestamp, event_type, file_path FROM events ORDER BY id DESC LIMIT 50")
        rows = cur.fetchall()
        return [{"id": r[0], "timestamp": r[1], "event_type": r[2], "file_path": r[3]} for r in rows]


# ========== Routes ==========
@app.route("/")
def dashboard():
    events = get_events()
    rows_html = ""
    for e in events:
        if e["file_path"] and e["file_path"].endswith(".jpg"):
            rows_html += f"""
            <tr>
                <td>{e['id']}</td>
                <td>{e['timestamp']}</td>
                <td>{e['event_type']}</td>
                <td><img class='thumb' src='/media/{Path(e['file_path']).name}'/></td>
            </tr>
            """

    html = f"""
    <html>
    <head>
        <title>Pi-Patrol Dashboard</title>
        <style>
            body {{
                background: #121212; color: #eee;
                font-family: Arial, sans-serif;
                margin: 0; padding: 0;
            }}
            .header {{
                background: #1f1f1f; padding: 20px;
                text-align: center; font-size: 28px; font-weight: bold;
            }}
            .container {{ padding: 20px; }}
            .section h2 {{
                border-left: 4px solid #00c853; padding-left: 10px; color: #00c853;
            }}
            table {{
                width: 100%; border-collapse: collapse; margin-top: 15px;
                background: #1e1e1e; border-radius: 10px; overflow: hidden;
            }}
            th, td {{ padding: 10px; text-align: left; }}
            tr:nth-child(even) {{ background: #252525; }}
            th {{ background: #00c853; color: black; }}
            img.thumb {{ max-width: 120px; border-radius: 6px; }}
            .enroll-btn, .toggle-btn {{
                margin-top: 10px; padding: 10px 20px;
                background: #00c853; color: black; border: none;
                border-radius: 6px; cursor: pointer; font-weight: bold;
            }}
            .enroll-btn:hover, .toggle-btn:hover {{ background: #00e676; }}
            input#personName {{
                padding: 8px; border-radius: 6px; border: none; width: 200px;
            }}
            #statusLabel {{
                margin-top: 10px; font-size: 18px;
                color: #00c853; font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="header">📹 Pi-Patrol Dashboard</div>
        <div class="container">
            <div class="section">
                <h2>Live Preview</h2>
                <div style="text-align:center;">
                    <img id="liveView" src="" alt="Preview not active"
                         style="max-width:100%; border-radius:10px; box-shadow:0 3px 10px rgba(0,0,0,0.2);" />
                    <div id="statusLabel">Preview Disabled</div>
                    <div style="margin-top:10px;">
                        <button id="toggleBtn" class="toggle-btn" onclick="togglePreview(true)">Enable Live Preview</button>
                    </div>
                    <div style="margin-top:10px;">
                        <input id="personName" type="text" placeholder="Enter name to enroll" />
                        <button class="enroll-btn" onclick="enrollFace()">Enroll</button>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2>Recent Events</h2>
                <table>
                    <tr><th>ID</th><th>Timestamp</th><th>Type</th><th>Preview</th></tr>
                    {rows_html}
                </table>
            </div>
        </div>

        <script>
        let liveEnabled = false;

        async function togglePreview(enable) {{
            try {{
                const res = await fetch("{TOGGLE_API}", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ enable }}),
                }});
                const data = await res.json();
                liveEnabled = data.live_preview;
                updatePreviewStatus();
            }} catch (err) {{
                alert("Error toggling preview: " + err);
            }}
        }}

        function updatePreviewStatus() {{
            const img = document.getElementById('liveView');
            const btn = document.getElementById('toggleBtn');
            const label = document.getElementById('statusLabel');

            if (liveEnabled) {{
                img.src = "http://localhost:5050/media/live.jpg?t=" + Date.now();
                btn.textContent = "Disable Live Preview";
                btn.onclick = () => togglePreview(false);
                label.textContent = "🟢 Live Preview Active";
                label.style.color = "#00e676";
            }} else {{
                img.src = "";
                btn.textContent = "Enable Live Preview";
                btn.onclick = () => togglePreview(true);
                label.textContent = "🔴 Preview Disabled";
                label.style.color = "#ff5252";
            }}
        }}

        function refreshLivePreview() {{
            if (!liveEnabled) return;
            const img = document.getElementById('liveView');
            img.src = 'http://localhost:5050/media/live.jpg?t=' + Date.now();
        }}

        async function updateFaceLabel() {{
            try {{
                const res = await fetch("{STATUS_API}");
                const data = await res.json();
                const label = document.getElementById('statusLabel');
                if (liveEnabled) {{
                    label.textContent = data.current_label === "Unknown"
                        ? "🔴 Unknown Person"
                        : "🟢 " + data.current_label;
                }}
            }} catch (e) {{
                console.log("Status check failed", e);
            }}
        }}

        function enrollFace() {{
            const name = document.getElementById('personName').value.trim();
            if (!name) {{ alert("Enter a name first."); return; }}
            const formData = new FormData();
            formData.append("name", name);
            fetch("{ENROLL_API}", {{ method: "POST", body: formData }})
                .then(res => res.json())
                .then(d => {{
                    if (d.success) alert("✅ Face enrolled: " + d.filename);
                    else alert("❌ Failed: " + (d.error || "Unknown error"));
                }})
                .catch(err => alert("Error: " + err));
        }}

        setInterval(refreshLivePreview, 1000);
        setInterval(updateFaceLabel, 1000);
        updatePreviewStatus();
        </script>
    </body>
    </html>
    """
    return html


@app.route("/media/<path:filename>")
def media(filename):
    if (EVENTS_DIR / filename).exists():
        return send_from_directory(EVENTS_DIR, filename)
    if (RECORDINGS_DIR / filename).exists():
        return send_from_directory(RECORDINGS_DIR, filename)
    return "File not found", 404


@app.route("/api/events")
def api_events():
    return jsonify(get_events())


if _name_ == "_main_":
    app.run(host="0.0.0.0", port=5001, debug=False)
