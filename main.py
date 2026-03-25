import threading
import time
import webbrowser
from app import app

def run_server():
    app.run(host="127.0.0.1", port=5001, debug=False, use_reloader=False)

if __name__ == "__main__":
    t = threading.Thread(target=run_server)
    t.start()
    time.sleep(1)
    webbrowser.open("http://127.0.0.1:5001")
    t.join()