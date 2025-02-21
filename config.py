import os

# 获取当前文件所在目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 基础路径配置
BASE_DATA_DIR = os.path.join(CURRENT_DIR, "../../memes_data")
MEMES_DIR = os.path.join(BASE_DATA_DIR, "memes")  # 表情包存储路径
MEMES_DATA_PATH = os.path.join(BASE_DATA_DIR, "memes_data.json")  # 类别描述数据文件路径

# 默认的类别描述
DEFAULT_CATEGORY_DESCRIPTIONS = {
    "angry": "表达愤怒或不满的场景",
    "happy": "表达开心或愉悦的场景",
    "sad": "表达悲伤或遗憾的场景",
    "surprised": "表达震惊或意外的场景",
    "confused": "表达困惑或不解的场景",
    "color": "表达调皮或暧昧的场景",
    "cpu": "表达思维停滞的场景",
    "fool": "表达自嘲或调侃的场景",
    "givemoney": "表达想要报酬的场景",
    "like": "表达喜爱之情的场景",
    "see": "表达关注或观察的场景",
    "shy": "表达害羞的场景",
    "work": "表达工作相关的场景",
    "scissors": "表达剪切或分割的场景",
    "reply": "表达等待回复的场景",
    "meow": "表达卖萌的场景",
    "baka": "表达责备的场景",
    "morning": "表达早安问候的场景",
    "sleep": "表达疲惫或休息的场景",
    "sigh": "表达叹息的场景"
} 