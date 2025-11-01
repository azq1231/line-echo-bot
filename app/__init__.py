import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import timedelta
import pytz

from flask import Flask
from dotenv import load_dotenv

# 載入 .env 檔案中的環境變數
load_dotenv()

# 導入資料庫模組，我們將在 create_app 中初始化它
import database as db

def create_app(start_scheduler=True):
    """
    建立並設定 Flask 應用程式的工廠函式。
    """
    # 建立 Flask 應用程式
    # 將 static_folder 指向根目錄的 'static' 資料夾，這與 Vite 的 build.outDir 設定一致。
    # 這是讓 Flask 能夠找到 Vue.js 打包後檔案的關鍵。
    app = Flask(__name__, 
                static_folder="../static", 
                static_url_path="/static",
                template_folder="../templates")

    # --- 核心設定 ---
    # 從環境變數讀取 SECRET_KEY，這對於生產環境至關重要
    app.secret_key = os.getenv("FLASK_SECRET_KEY")
    if not app.secret_key:
        # 在生產環境中，FLASK_SECRET_KEY 必須被設定，否則會導致 session 失效
        raise ValueError("FLASK_SECRET_KEY 環境變數未設定。請在 .env 或環境中設定一個安全的隨機字串。")

    # 強化 Session 安全性
    app.config['SESSION_PERMANENT'] = True
    app.permanent_session_lifetime = timedelta(days=30)

    # --- 全域變數 ---
    # 將這些變數附加到 app.config，以便在應用程式的其他地方（例如藍圖中）使用
    app.config['LINE_CHANNEL_TOKEN'] = os.getenv("LINE_CHANNEL_TOKEN")
    app.config['LINE_CHANNEL_SECRET'] = os.getenv("LINE_CHANNEL_SECRET")
    app.config['LINE_LOGIN_CHANNEL_ID'] = os.getenv("LINE_LOGIN_CHANNEL_ID")
    app.config['LINE_LOGIN_CHANNEL_SECRET'] = os.getenv("LINE_LOGIN_CHANNEL_SECRET")
    app.config['TAIPEI_TZ'] = pytz.timezone('Asia/Taipei')

    # --- 初始化資料庫 ---
    with app.app_context():
        db.init_database()

    # --- 設定日誌 ---
    # 關鍵：設定 app logger 的等級，否則在生產模式下它只會處理 WARNING 等級以上的訊息
    if not app.debug:
        app.logger.setLevel(logging.INFO)

    # 為了避免在 debug 模式重載時重複新增 handler，
    # 我們檢查 logger 中是否已經有 RotatingFileHandler 類型的 handler。
    if not any(isinstance(handler, RotatingFileHandler) for handler in app.logger.handlers):
        # 建立一個日誌檔案處理器
        file_handler = RotatingFileHandler(
            'app.log', 
            maxBytes=1_000_000, 
            backupCount=3, 
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO) # 設定只記錄 INFO 等級以上的訊息
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        # 將檔案處理器加入到 app 的 logger 中
        app.logger.addHandler(file_handler)

    # --- 註冊藍圖 (Blueprints) ---
    from .routes.auth import auth_bp
    from .routes.admin import admin_bp, api_admin_bp # This will now import from the new __init__.py
    from .routes.booking import booking_bp
    from .routes.webhook import webhook_bp
    from .routes.user import user_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_admin_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(webhook_bp)
    app.register_blueprint(user_bp)

    # --- 上下文處理器 ---
    @app.context_processor
    def inject_feature_flags():
        """將功能開關的狀態注入到所有模板中，以便動態顯示/隱藏導覽列項目。"""
        return {
            'feature_schedule_enabled': db.get_config('feature_schedule_enabled', 'true') != 'false',
            'feature_closed_days_enabled': db.get_config('feature_closed_days_enabled', 'true') != 'false',
            'feature_booking_enabled': db.get_config('feature_booking_enabled', 'true') != 'false',
        }

    # --- 初始化排程器 ---
    # 根據傳入的參數決定是否啟動排程器
    if start_scheduler:
        from .scheduler import init_scheduler
        init_scheduler(app)
    else:
        app.logger.info("此進程不啟動排程器。")

    return app