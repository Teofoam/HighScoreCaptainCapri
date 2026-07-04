import os
import random
import requests
import glob
import re
import sys

# 1. Grab our secrets from GitHub
TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
CHAT_ID = os.environ['TELEGRAM_CHAT_ID']

# 2. 读取所有题目和权重
problems = []
# 扫描 problems 文件夹下的所有 markdown 文件
md_files = glob.glob('problems/*.md')

for file_path in md_files:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
        # 用正则提取权重，默认权重为 1
        weight_match = re.search(r'weight:\s*(\d+)', content, re.IGNORECASE)
        weight = int(weight_match.group(1)) if weight_match else 1
        
        # 提取图片路径 (匹配 ![...](path) 格式)
        img_match = re.search(r'!\[.*?\]\((.*?)\)', content)
        img_path = img_match.group(1) if img_match else None
        
        # 清理掉头部配置，只保留正文
        text_content = re.sub(r'^---.*?---\n', '', content, flags=re.DOTALL).strip()
        
        problems.append({
            'file': file_path,
            'content': text_content,
            'weight': weight,
            'img_path': img_path
        })

# 3. 按权重随机抽取一道题 (核心逻辑！)
weights = [p['weight'] for p in problems]
daily_problem = random.choices(problems, weights=weights, k=1)[0]

# 4. 推送到 Telegram
def push_to_telegram(problem):
    # 去掉了可能会引起冲突的 Markdown 符号，改为纯文本标记
    message = f"🌟 Time to soar high! Daily Problem:\n\n{problem['content']}"
    
    if problem['img_path'] and os.path.exists(problem['img_path']):
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        with open(problem['img_path'], 'rb') as photo:
            # 移除 parse_mode，防止 LaTeX 公式导致解析报错
            payload = {'chat_id': CHAT_ID, 'caption': message[:1024]}
            files = {'photo': photo}
            response = requests.post(url, data=payload, files=files)
            
    else:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            'chat_id': CHAT_ID,
            'text': message
            # 同样移除 parse_mode
        }
        response = requests.post(url, json=payload)
        
    return response

response = push_to_telegram(daily_problem)

# 5. 严格的错误处理机制
if response.status_code == 200:
    print(f"✅ Successfully pushed {daily_problem['file']} to phone!")
else:
    # 如果失败，打印 Telegram 的真实报错信息
    print(f"❌ Failed to push! Telegram API Error: {response.text}")
    # 强制让 Python 以错误状态退出，这样 GitHub Action 就会变红！
    sys.exit(1)