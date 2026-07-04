import os
import random
import requests
import glob
import re

# 1. 获取密钥
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
    message = f"🌟 **Time to soar high! Daily Problem:**\n\n{problem['content']}"
    
    # 情况 A：如果题目包含图片
    if problem['img_path'] and os.path.exists(problem['img_path']):
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        with open(problem['img_path'], 'rb') as photo:
            payload = {'chat_id': CHAT_ID, 'caption': message[:1024], 'parse_mode': 'Markdown'}
            files = {'photo': photo}
            response = requests.post(url, data=payload, files=files)
            
    # 情况 B：纯文本题目
    else:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }
        response = requests.post(url, json=payload)
        
    return response

response = push_to_telegram(daily_problem)

if response.status_code == 200:
    print(f"Successfully pushed {daily_problem['file']} to phone!")
else:
    print("Failed:", response.text)