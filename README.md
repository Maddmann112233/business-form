# MOH Admin / Business Owner App

A Streamlit app that reads/writes to Google Sheets and triggers n8n webhooks for MOH data requests.

---

## Table of Contents
- [Quick Start](#quick-start)
- [Requirements](#requirements)
- [Local Setup](#local-setup)
- [Environment Variables](#environment-variables)
- [Running the App](#running-the-app)
- [Project Structure](#project-structure)
- [Git Workflow](#git-workflow)
- [Commit Messages](#commit-messages)
- [Pull Requests](#pull-requests)
- [Handling Merge Conflicts](#handling-merge-conflicts)
- [Versioning & Releases](#versioning--releases)
- [Testing](#testing)
- [CI/CD](#cicd)
- [License](#license)

---

## Quick Start

```bash
# 1) Clone
git clone <YOUR_REPO_URL>.git
cd <YOUR_REPO_NAME>

# 2) Create & activate venv
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3) Install deps
pip install -r requirements.txt

# 4) Run
streamlit run streamlit_app.py
