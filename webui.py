import os
import multiprocessing
import requests
from flask import (
    Flask,
    render_template,
    send_from_directory,
    request,
    redirect,
    url_for,
    session,
)
from .backend.api import api
from .utils import generate_secret_key
from .config import MEMES_DIR
import psutil

app = Flask(__name__)

# 注册API蓝图
app.register_blueprint(api, url_prefix="/api")

SERVER_LOGIN_KEY = None
SERVER_PROCESS = None

def is_webui_running(port=5000):
    """检查 WebUI 是否已经在运行"""
    try:
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.status == 'LISTEN':
                return True
        return False
    except:
        return False

def kill_existing_webui(port=5000):
    """关闭已存在的 WebUI 进程"""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'connections']):
            try:
                for conn in proc.connections():
                    if conn.laddr.port == port and conn.status == 'LISTEN':
                        proc.terminate()
                        proc.wait(timeout=5)
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except:
        pass
    return False

@app.before_request
def require_login():
    allowed_endpoints = ["login", "static"]
    if request.endpoint not in allowed_endpoints and not session.get("authenticated"):
        return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("authenticated"):
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        key = request.form.get("key")
        if key == SERVER_LOGIN_KEY:
            session["authenticated"] = True
            return redirect(url_for("index"))
        else:
            error = "秘钥错误，请重试。"
    return render_template("login.html", error=error)

@app.route("/")
def index():
    if not session.get("authenticated"):
        return redirect(url_for("login"))
    return render_template("index.html")

@app.route("/memes/<category>/<filename>")
def serve_emoji(category, filename):
    category_path = os.path.join(MEMES_DIR, category)
    if os.path.exists(os.path.join(category_path, filename)):
        return send_from_directory(category_path, filename)
    else:
        return "File not found: " + os.path.join(category_path, filename), 404

@app.route("/shutdown_api", methods=["POST"])
def shutdown_api():
    func = request.environ.get("werkzeug.server.shutdown")
    if func is None:
        raise RuntimeError("无法关闭服务器：不是在 Werkzeug 环境中运行？")
    func()
    return "Server shutting down..."

def run_server(port=5000):
    """运行服务器"""
    app.run(host="0.0.0.0", port=port)

def start_server(config=None):
    """启动服务器"""
    global SERVER_LOGIN_KEY, SERVER_PROCESS
    
    # 如果已有进程在运行，先关闭它
    port = config.get("webui_port", 5000) if config else 5000
    if is_webui_running(port):
        print(f"检测到端口 {port} 已被占用，尝试关闭现有进程...")
        kill_existing_webui(port)
    
    SERVER_LOGIN_KEY = generate_secret_key(8)
    print("当前秘钥为:", SERVER_LOGIN_KEY)

    app.secret_key = os.urandom(16)

    if config is not None and hasattr(config, 'get'):
        app.config["PLUGIN_CONFIG"] = {
            "img_sync": config.get("img_sync"),
            "category_manager": config.get("category_manager"),
            "webui_port": port
        }

    # 启动新进程
    SERVER_PROCESS = multiprocessing.Process(target=run_server, args=(port,))
    SERVER_PROCESS.start()
    return SERVER_LOGIN_KEY, SERVER_PROCESS

def shutdown_server(server_process):
    """关闭服务器"""
    try:
        if server_process and server_process.is_alive():
            plugin_config = app.config.get("PLUGIN_CONFIG", {})
            port = plugin_config.get("webui_port", 5000)
            try:
                requests.post(f"http://127.0.0.1:{port}/shutdown_api")
            except:
                pass
            server_process.terminate()
            server_process.join(timeout=5)
            if server_process.is_alive():
                server_process.kill()
    except Exception as e:
        print("关闭服务器时出错:", e)

def create_app(config=None):
    app = Flask(__name__)
    
    if config is not None and hasattr(config, 'get'):
        app.config["PLUGIN_CONFIG"] = {
            "img_sync": config.get("img_sync"),
            "category_manager": config.get("category_manager"),
            "webui_port": config.get("webui_port", 5000)
        }
    else:
        print("警告: 配置格式不正确")

    # 注册蓝图
    from .backend.api import api
    app.register_blueprint(api, url_prefix="/api")
    
    return app
