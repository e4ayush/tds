import datetime
import subprocess
import os
from dotenv import load_dotenv
import requests
from flask import Flask, request, jsonify

# It’s safer to use environment variables for sensitive information
# Ensure LLM_API_KEY and GITHUB_PAT are set in your environment
# e.g., using .env files or setting them directly in the OS environment
# (You can set environment variables in your IDE or server environment)
# Example: export LLM_API_KEY="your-api-key" or use a .env file

load_dotenv()

# Now you can access the variables
llm_key = os.getenv("LLM_API_KEY")
github_pat = os.getenv("GITHUB_PAT")

OUR_SECRET = "my-super-secret-key"
app = Flask(__name__)

def generate_code_from_brief(brief):
    """Uses AIPipe to generate HTML code from a brief."""
    
    # Read the key using the correct environment variable name "LLM_API_KEY"
    llm_key = os.getenv("LLM_API_KEY")
    if not llm_key:
        print("FATAL: LLM_API_KEY environment variable is not set.")
        return None

    api_url = "https://aipipe.org/openrouter/v1/chat/completions"
    headers = {
        # Use the 'llm_key' variable in the Authorization header
        "Authorization": f"Bearer {llm_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [
            {
                "role": "user",
                "content": f"""
                Based on the following brief, create a complete, single-page web application.
                The application must be self-contained in a single HTML file, including any CSS or JavaScript.
                Brief: "{brief}"
                Return only the full HTML code.
                """
            }
        ]
    }
    try:
        response = requests.post(api_url, headers=headers, json=data)
        response.raise_for_status()
        result_json = response.json()
        generated_code = result_json['choices'][0]['message']['content']
        return generated_code
    except Exception as e:
        print(f"An error occurred with AIPipe: {e}")
        return None

def deploy_to_github(repo_name):
    """Initializes a git repo, creates a GitHub repo, and pushes the code."""
    try:
        print("Initializing git repository...")
        DEVNULL = open(os.devnull, 'w')
        subprocess.run(["git", "init"], check=True, stdout=DEVNULL, stderr=DEVNULL)
        
        # Add all files, including index.html and LICENSE
        subprocess.run(["git", "add", "."], check=True, stdout=DEVNULL, stderr=DEVNULL) 
        
        subprocess.run(["git", "commit", "-m", "Initial commit"], check=True, stdout=DEVNULL, stderr=DEVNULL)
        
        # Get the commit SHA
        result = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
        commit_sha = result.stdout.strip()
        print(f"Got commit SHA: {commit_sha}")

        print(f"Creating GitHub repo '{repo_name}' and pushing code...")
        subprocess.run(
            ["gh", "repo", "create", repo_name, "--public", "--source=.", "--push"],
            check=True, capture_output=True, text=True
        )
        print("Deployment to GitHub successful!")
        return commit_sha
    except subprocess.CalledProcessError as e:
        print(f"An error occurred during GitHub deployment: {e}")
        print(f"Stderr: {e.stderr}")
        return None

def notify_evaluation_server(request_data, repo_url, commit_sha, pages_url):
    """Sends a POST request to the evaluation_url."""
    notification_data = {
        "email": request_data.get("email"),
        "task": request_data.get("task"),
        "round": request_data.get("round"),
        "nonce": request_data.get("nonce"),
        "repo_url": repo_url,
        "commit_sha": commit_sha,
        "pages_url": pages_url
    }

    eval_url = request_data.get("evaluation_url")
    if not eval_url:
        print("No evaluation_url found in request.")
        return False

    print(f"Sending notification to {eval_url}...")
    try:
        response = requests.post(eval_url, json=notification_data)
        response.raise_for_status()
        print("Successfully notified evaluation server.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to notify evaluation server: {e}")
        return False

@app.route('/api-endpoint', methods=['POST'])
def handle_request():
    data = request.get_json()

    if data.get("secret") != OUR_SECRET:
        return jsonify({"error": "Invalid secret"}), 403

    brief = data.get("brief")
    html_code = generate_code_from_brief(brief)
    if not html_code:
        return jsonify({"error": "Failed to generate code"}), 500

    task_id = data.get("task")
    round_num = data.get("round")
    
    # Variables defined upfront (Logic Flow Fix)
    github_username = "e4ayush" # Your GitHub username
    repo_url = f"https://github.com/{github_username}/{task_id}"
    pages_url = f"https://{github_username}.github.io/{task_id}/"
    commit_sha = None

    if round_num == 1:
        print("--- Round 1: Creating new repository ---")
        
        # The local git repo must be cleaned up before creating a new one
        if os.path.exists(".git"):
            # Check OS and use appropriate removal command
            if os.name == 'nt': # Windows
                subprocess.run("rmdir /s /q .git", shell=True, check=True)
            else: # Linux/macOS
                subprocess.run("rm -rf .git", shell=True, check=True)

        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html_code)

        license_content = f"""MIT License
Copyright (c) {datetime.datetime.now().year} {github_username}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""
        with open("LICENSE", "w", encoding="utf-8") as f:
            f.write(license_content)
        
        # --- README.md CREATION (REQUIRED FOR EVALUATION) ---
        readme_content = f"""# LLM Generated App: {task_id}
        
## Summary
This application was automatically generated by an LLM based on the project brief.
        
## Setup & Usage
This is a single-page web application hosted on GitHub Pages.
        
## License
This project is released under the MIT License (see LICENSE file).
"""
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(readme_content)
        # --- END README.md CREATION ---
        
        commit_sha = deploy_to_github(task_id)

    else:
        print(f"--- Round {round_num}: Updating existing repository ---")
        commit_sha = update_repository(repo_url, html_code, github_username)

    if not commit_sha:
        return jsonify({"error": "Failed to deploy to GitHub"}), 500

    notify_evaluation_server(data, repo_url, commit_sha, pages_url)
    return jsonify({"status": f"round_{round_num}_deployed_and_notified"}), 200

def update_repository(repo_url, new_html_code, github_username):
    """Clones a repo, updates a file, and pushes the changes."""
    
    # Securely read the PAT
    github_pat = os.getenv("GITHUB_PAT")
    if not github_pat:
        print("FATAL: GITHUB_PAT environment variable is not set for repository update.")
        return None 
    
    repo_name = repo_url.split('/')[-1]
    
    # Construct clone URL using the PAT
    clone_url = f"https://{github_pat}@github.com/{github_username}/{repo_name}.git"

    try:
        print(f"Cloning {repo_name}...")
        subprocess.run(["git", "clone", clone_url], check=True, capture_output=True)

        # Change directory into the new folder
        os.chdir(repo_name)

        print("Updating index.html...")
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(new_html_code)

        print("Committing and pushing changes...")
        subprocess.run(["git", "add", "index.html"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Revise code based on new brief"], check=True, capture_output=True)
        subprocess.run(["git", "push"], check=True, capture_output=True)

        result = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
        commit_sha = result.stdout.strip()

        # Go back to the parent directory and clean up
        os.chdir("..")
        if os.name == 'nt': # Windows
            subprocess.run(f"rmdir /s /q {repo_name}", shell=True, check=True)
        else: # Linux/macOS
            subprocess.run(f"rm -rf {repo_name}", shell=True, check=True)

        print("Repository update successful!")
        return commit_sha
        
    except Exception as e:
        print(f"An error occurred during repository update: {e}")
        return None

if __name__ == '__main__':
    app.run(port=5000, debug=True)
