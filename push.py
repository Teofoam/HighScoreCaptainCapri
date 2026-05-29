import os
import csv
import random
import requests

# 1. Grab our secrets from GitHub
TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
CHAT_ID = os.environ['TELEGRAM_CHAT_ID']

# 2. Read the problems from our CSV database
problems = []
with open('problems.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        problems.append(row)

# 3. Pick a random problem
daily_problem = random.choice(problems)

# 4. Format the message for your phone
message = f"🚀 **Time to Soar High! Daily {daily_problem['Subject']}**\n\n"
message += f"**Topic:** {daily_problem['Topic']}\n\n"
message += f"{daily_problem['ProblemText']}\n"

# 5. Push to Telegram
url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
payload = {
    "chat_id": CHAT_ID,
    "text": message,
    "parse_mode": "Markdown"
}

response = requests.post(url, json=payload)
if response.status_code == 200:
    print("Successfully pushed to phone!")
else:
    print("Failed:", response.text)
