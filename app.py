from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
import re
import os
import time
from dotenv import load_dotenv
import base64

load_dotenv()

app = Flask(__name__)

GITHUB_API_URL = "https://api.github.com/search/users"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "User-Agent": "MyEmailExtractorApp"
}

EMAIL_PATTERN = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"

# ❌ GitHub 기본 자동 이메일 필터
def is_valid_email(email):
    return email and not any([
        email.endswith("@users.noreply.github.com"),
        email == "git@github.com",
        email.startswith("noreply")
    ])

# ✅ 1차 시도: GitHub 프로필 페이지에서 이메일 추출
def extract_email_from_profile_html(username):
    url = f"https://github.com/{username}"
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        print(f"🌐 Fetching profile page: {url}")
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            email_li = soup.find("li", {"itemprop": "email"})
            if email_li:
                email_a = email_li.find("a", href=True)
                if email_a and email_a["href"].startswith("mailto:"):
                    email = email_a["href"].replace("mailto:", "").strip()
                    if is_valid_email(email):
                        print(f"📧 Found email in profile: {email}")
                        return email

            # 백업 정규식 추출
            emails = re.findall(EMAIL_PATTERN, soup.text)
            for email in emails:
                if is_valid_email(email):
                    print(f"📬 Backup email from HTML: {email}")
                    return email
    except Exception as e:
        print(f"❌ Error fetching profile for {username}: {e}")
    return None

# ✅ 2차 시도: 가장 인기 있는 repo의 README.md에서 이메일 추출
def extract_email_from_readme(username):
    try:
        repo_url = f"https://api.github.com/users/{username}/repos?sort=stars&per_page=1"
        repo_res = requests.get(repo_url, headers=HEADERS)
        if repo_res.status_code != 200:
            print(f"❌ Failed to fetch repos for {username}")
            return None

        repos = repo_res.json()
        if not repos:
            print(f"📭 No repos found for {username}")
            return None

        repo_name = repos[0]["name"]
        readme_url = f"https://api.github.com/repos/{username}/{repo_name}/readme"
        readme_res = requests.get(readme_url, headers=HEADERS)
        if readme_res.status_code != 200:
            print(f"📄 No README in {repo_name}")
            return None

        content = readme_res.json().get("content", "")
        decoded_readme = base64.b64decode(content).decode("utf-8", errors="ignore")
        emails = re.findall(EMAIL_PATTERN, decoded_readme)
        for email in emails:
            if is_valid_email(email):
                print(f"📘 Found email in README: {email}")
                return email
    except Exception as e:
        print(f"❌ Error reading README for {username}: {e}")
    return None

# 🧠 전체 추출 로직
def extract_email(username):
    email = extract_email_from_profile_html(username)
    if email:
        return email
    return extract_email_from_readme(username)

# 🌐 검색 및 이메일 수집
@app.route("/", methods=["GET", "POST"])
def index():
    users = []
    if request.method == "POST":
        language = request.form.get("language")
        location = request.form.get("location")

        query = f"language:{language}+location:{location}"
        url = f"{GITHUB_API_URL}?q={query}&per_page=20"

        try:
            response = requests.get(url, headers=HEADERS)
            if response.status_code == 200:
                data = response.json()
                raw_users = data.get("items", [])
                for user in raw_users:
                    username = user.get("login")
                    print(f"\n🔎 Extracting email for: {username}")
                    email = extract_email(username)
                    time.sleep(1)  # Rate limit 회피

                    if email:  # ✅ 이메일이 있을 때만 결과에 추가
                        user["email"] = email
                        users.append(user)
        except requests.exceptions.RequestException as e:
            print("❌ GitHub user search failed:", e)

    return render_template("index.html", users=users)


if __name__ == "__main__":
    app.run(debug=True)
