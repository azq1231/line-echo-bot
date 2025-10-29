from app import create_app
from dotenv import load_dotenv
import os

load_dotenv()

app = create_app()

if __name__ == "__main__":
    # 透過環境變數 FLASK_DEBUG 來決定是否開啟除錯模式
    app.run(host="0.0.0.0", port=5000)