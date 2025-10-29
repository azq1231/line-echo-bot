from app import create_app
from dotenv import load_dotenv
import os

load_dotenv()

app = create_app()

if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() in ['true', '1', 't']
    
    if not debug_mode:
        app.run(host="0.0.0.0", port=5000, debug=False) 
    else:
        app.run(host="0.0.0.0", port=5000, debug=True)