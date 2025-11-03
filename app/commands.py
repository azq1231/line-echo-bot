import click
from flask.cli import with_appcontext

import database as db

@click.command('set-admin')
@with_appcontext
def set_admin_command():
    """將一位使用者設定為管理員。"""
    users = db.get_all_users()
    if not users:
        print("資料庫中沒有任何使用者。請先讓至少一位使用者加入好友並登入網站。")
        return

    print("請選擇要設為管理員的使用者：")
    for i, user in enumerate(users):
        print(f"{i + 1}: {user['name']} (ID: {user['user_id']})")

    while True:
        try:
            choice = input("請輸入使用者編號: ")
            user_index = int(choice) - 1
            if 0 <= user_index < len(users):
                selected_user = users[user_index]
                db.update_user_admin_status(selected_user['user_id'], True)
                print(f"✅ 成功將「{selected_user['name']}」設為管理員。")
                break
            else:
                print("無效的編號，請重新輸入。")
        except (ValueError, IndexError):
            print("輸入無效，請輸入數字編號。")

def init_commands(app):
    """向 Flask app 註冊所有自訂指令。"""
    app.cli.add_command(set_admin_command)