from app import create_app
from dotenv import load_dotenv
import os

load_dotenv()

# 在 Gunicorn 中，我們將使用 --preload 參數來確保應用只在主進程中初始化一次。
# 在 Flask 開發模式下，WERKZEUG_RUN_MAIN 環境變數會被用來防止在子進程中重複啟動。
# 因此，我們可以在 create_app 中統一處理。
is_main_process = os.environ.get('WERKZEUG_RUN_MAIN') != 'true'
app = create_app(start_scheduler=is_main_process)

if __name__ == "__main__":
    # 這裡的 debug=True 會導致 Flask 啟動一個子進程，
    # is_main_process 的判斷會確保排程器只在主進程啟動。
    app.run(host="0.0.0.0", port=5000)