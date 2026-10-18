from flask import Flask

app = Flask(__name__)


@app.route("/")
def index():
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Hello</title>
</head>
<body>
  <h1>Hello from Julieta</h1>
</body>
</html>"""


if __name__ == "__main__":
    app.run(debug=True)