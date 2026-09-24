from urllib.parse import urlparse

from flask import Flask, redirect, render_template_string, url_for

from config import settings

app = Flask(__name__)

STYLE = """<style>
body { background:#14161a; color:#e8e8e8; font:16px sans-serif; margin:40px; }
main { max-width:760px; margin:auto; background:#20242b; padding:32px; border-radius:8px; }
a { color:#777; font-size:12px; }
button { padding:12px 18px; margin:8px; cursor:pointer; }
.modal { position:fixed; inset:0; background:#000b; display:grid; place-items:center; }
.dialog { background:white; color:#111; padding:28px; max-width:420px; box-shadow:0 8px 30px #000; }
.secondary { background:#eee; border:0; }
</style>"""

ACCOUNT = """<main>
  <h1>Acme Video membership</h1>
  <p>Plan: Premium monthly</p><p>Next charge: $19.99</p>
  <a id="cancel-link" href="{{ url_for('retention') }}">Need to cancel?</a>
</main>
"""

PAGE = "<!doctype html><title>Acme Video Account</title>" + STYLE + ACCOUNT

# The retention offer is a modal laid over the account page.
RETENTION = "<!doctype html><title>Stay with us</title>" + STYLE + ACCOUNT + """
<div class="modal"><div class="dialog">
<h2>Before you go...</h2><p>Keep Premium for only $9.99/month.</p>
<button onclick="location.href='{{ url_for('account') }}'">Keep my membership</button>
<button class="secondary" onclick="location.href='{{ url_for('confirm_cancel') }}'">Continue to cancellation</button>
</div></div>
"""

CONFIRM = "<!doctype html><title>Confirm cancellation</title>" + STYLE + """<main><h1>One last confirmation</h1>
<p>Your benefits remain active until the end of the period.</p>
<a href="{{ url_for('cancelled') }}">Confirm cancellation</a>
<a href="{{ url_for('account') }}">Go back</a></main>
"""

DONE = "<!doctype html><title>Cancelled</title>" + STYLE + """<main><h1>Cancellation requested</h1><p>Your sandbox membership is cancelled.</p></main>"""

@app.get("/")
def account():
    return render_template_string(PAGE)

@app.get("/retention")
def retention():
    return render_template_string(RETENTION)

@app.get("/confirm-cancel")
def confirm_cancel():
    return render_template_string(CONFIRM)

@app.get("/cancelled")
def cancelled():
    return render_template_string(DONE)

if __name__ == "__main__":
    # Loopback only; the port follows MOCK_SITE_URL so the agent's origin check matches.
    app.run(host="127.0.0.1", port=urlparse(settings.mock_site_url).port or 5000, debug=False)
