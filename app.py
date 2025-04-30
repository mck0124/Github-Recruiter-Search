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

def is_valid_email(email):
    return email and not any([
        email.endswith("@users.noreply.github.com"),
        email == "git@github.com",
        email.startswith("noreply")
    ])

# ✅ 프로필에서 이메일 추출
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

            emails = re.findall(EMAIL_PATTERN, soup.text)
            for email in emails:
                if is_valid_email(email):
                    print(f"📬 Backup email from HTML: {email}")
                    return email
    except Exception as e:
        print(f"❌ Error fetching profile for {username}: {e}")
    return None

# ✅ README에서 이메일 추출
def extract_email_from_readme(username):
    try:
        repo_url = f"https://api.github.com/users/{username}/repos?sort=stars&per_page=1"
        repo_res = requests.get(repo_url, headers=HEADERS)
        if repo_res.status_code != 200:
            return None

        repos = repo_res.json()
        if not repos:
            return None

        repo_name = repos[0]["name"]
        readme_url = f"https://api.github.com/repos/{username}/{repo_name}/readme"
        readme_res = requests.get(readme_url, headers=HEADERS)
        if readme_res.status_code != 200:
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

# ✅ 이메일 추출 종합
def extract_email(username):
    email = extract_email_from_profile_html(username)
    if email:
        return email
    return extract_email_from_readme(username)

# ✅ 점수 계산
def get_user_score(username):
    try:
        user_url = f"https://api.github.com/users/{username}"
        user_res = requests.get(user_url, headers=HEADERS)
        if user_res.status_code != 200:
            return 0, {}

        user_info = user_res.json()
        public_repos = user_info.get("public_repos", 0)
        followers = user_info.get("followers", 0)

        repo_url = f"https://api.github.com/users/{username}/repos?per_page=100"
        repo_res = requests.get(repo_url, headers=HEADERS)
        if repo_res.status_code != 200:
            return 0, {}

        repos = repo_res.json()
        total_stars = sum(repo.get("stargazers_count", 0) for repo in repos)
        total_forks = sum(repo.get("forks_count", 0) for repo in repos)

        score = (
            public_repos * 1 +
            followers * 2 +
            total_stars * 3 +
            total_forks * 1.5
        )

        details = {
            "followers": followers,
            "public_repos": public_repos,
            "total_stars": total_stars,
            "total_forks": total_forks
        }

        return round(score, 1), details
    except Exception as e:
        print(f"❌ Failed to calculate score for {username}: {e}")
        return 0, {}


# ✅ 메인 뷰
@app.route("/", methods=["GET", "POST"])
def index():
    users = []
    if request.method == "POST":
        language = request.form.get("language")
        location = request.form.get("location")

        query = f"language:{language}+location:{location}"
        url = f"{GITHUB_API_URL}?q={query}&per_page=100"

        try:
            response = requests.get(url, headers=HEADERS)
            if response.status_code == 200:
                data = response.json()
                raw_users = data.get("items", [])
                for user in raw_users:
                    username = user.get("login")
                    print(f"\n🔎 Extracting email for: {username}")
                    email = extract_email(username)
                    time.sleep(1)
                    if email:
                        score, details = get_user_score(username)
                        user["email"] = email
                        user["score"] = score
                        user.update(details)  # 요소들 추가
                        users.append(user)
        except requests.exceptions.RequestException as e:
            print("❌ GitHub user search failed:", e)

    users.sort(key=lambda u: u["score"], reverse=True)
    return render_template("index.html", users=users)

if __name__ == "__main__":
    app.run(debug=True)
