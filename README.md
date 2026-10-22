# 🍱 Surplus Donation

### Ziro.Digital Agentic AI Hackathon 2026 | Social Impact & Sustainability AI

**Turning surplus into meaningful meals. 💚**

Surplus Donation is a web-based food donation platform designed to connect restaurants with NGOs to help redistribute surplus food, reduce food waste, and support communities in need.

This project was developed for the **Ziro.Digital Agentic AI Hackathon 2026**, based on the assigned problem statement **Surplus Food Donation Matcher**.

---

## 🌍 About the Project

Restaurants may have surplus prepared food while NGOs need food to support communities. Coordinating food availability, quantity, preparation time, food safety, and pickup arrangements can be challenging.

Surplus Donation provides a centralized website where restaurants can share surplus food donations and NGOs can review and respond to available donation opportunities.

The project focuses on improving donation coordination, tracking donation status, and supporting safer pickup workflows.

## 🎯 Problem Statement

- **Hackathon:** Ziro.Digital Agentic AI Hackathon 2026
- **Category:** Industry / Social Impact & Sustainability AI
- **Assigned Problem:** Surplus Food Donation Matcher
- **Demo Target:** Mock donation platform
- **Participation:** Solo entry

### Objective

Build a solution that helps match restaurant surplus food with an NGO that has the capacity to collect it safely within the available time window.

## ✨ Features

- **User Authentication:** Login and registration for supported user roles.
- **Restaurant Dashboard:** Submit and manage surplus food donation details.
- **NGO Dashboard:** View available donations and respond to suitable opportunities.
- **Donation Management:** Maintain donation information and status.
- **Pickup Coordination:** Support pickup request and collection workflows.
- **Food Safety Awareness:** Consider food preparation time and pickup windows.
- **NGO Capacity Consideration:** Account for NGO availability and collection capacity when evaluating a match.
- **Location Management:** Support location updates and reconfirmation when required.
- **Reviewer Access:** Provide a reviewer role within the application.
- **Test Case Support:** Organize demonstration and verification of the required scenarios.
- **SQLite Database:** Store application records persistently.

*Features and workflows should be considered implemented only to the extent supported by the current application code.*

## 🔄 Proposed Workflow

1. **Collect Donation Details**  
   Record the food type, quantity, preparation time, and pickup window.

2. **Evaluate Food Safety**  
   Check whether the donation falls within the applicable safety window.

3. **Check NGO Capacity**  
   Identify an NGO that can collect the available donation within the required time.

4. **Propose a Match**  
   Present the potential donation match and its supporting information.

5. **Request Human Approval**  
   Ask for approval before carrying out consequential actions.

6. **Create Pickup Request**  
   Submit the pickup request through the supported platform workflow.

7. **Verify Pickup Status**  
   Check whether the NGO accepted the pickup request. Do not report a donation as collected without confirmation.

8. **Handle Location Changes**  
   If the NGO changes the drop-off location, obtain restaurant reconfirmation before proceeding.

## 🧪 Official Hackathon Test Cases

The following scenarios are specified in the official problem statement.

| Test Case | Scenario | Expected Result |
|---|---|---|
| TC1 | Fresh food with NGO capacity | Pickup request created |
| TC2 | Food prepared too long ago | Rejected for safety |
| TC3 | NGO has not accepted | Not reported as collected |
| TC4 | NGO changes drop-off location | Reconfirmed with restaurant |

Each test should include the input, expected result, actual result, and supporting evidence. The table describes expected outcomes; it does not claim that all tests have already passed.

## 🛠️ Tools & Technologies Used

### Development Technologies

- **Python** — Backend programming and application logic.
- **Flask** — Web application framework and routing.
- **HTML** — Page structure.
- **CSS** — Styling and responsive UI improvements.
- **JavaScript** — Frontend interactions where implemented.
- **Jinja2** — Dynamic HTML templates.
- **SQLite** — Database storage.
- **Visual Studio Code** — Code editing and development.
- **Git** — Version control.
- **GitHub** — Source code hosting and project documentation.

### AI-Assisted Development

- **ChatGPT (OpenAI)** — Used as a development assistant for code-writing guidance, debugging support, UI improvements, troubleshooting, and README documentation.

ChatGPT was used to assist with development. This does not, by itself, mean that an autonomous AI agent or an LLM-powered matching system is integrated into the running website.

## 🏗️ System Architecture

```text
        Restaurant / NGO / Reviewer
                    |
                    v
             Web Interface
          HTML, CSS, Jinja2
                    |
                    v
               Flask App
       Authentication and Routes
                    |
                    v
           Donation Workflows
       Submission, Review, Pickup
                    |
                    v
               SQLite DB
                    |
                    v
        Donation and Pickup Status
```

This diagram represents the application's general web architecture. External integrations and autonomous agent components should be added to the diagram once they are implemented and verified.

## 🚀 Getting Started

### Prerequisites

- Python 3
- pip
- Visual Studio Code (recommended)

### 1. Clone the Repository

Replace the placeholder with your actual GitHub repository URL.

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
```

### 2. Open the Project Folder

```bash
cd YOUR_PROJECT_FOLDER
```

### 3. Install Dependencies

If the project contains a `requirements.txt` file, run:

```bash
pip install -r requirements.txt
```

Otherwise, install the dependencies listed in your project's actual import statements and configuration.

### 4. Start the Flask Application

```bash
python app.py
```

### 5. Open the Website

Visit the following address in your browser while the local Flask server is running:

```text
http://127.0.0.1:5000/
```

**Note:** These instructions assume that `app.py` is the application's entry point and that the required configuration and database files are present.

## 🗄️ Database

The application uses SQLite to store its records.

The database supports the application's configured workflows, such as user accounts and donation-related information.

Keep existing database files when updating the application. Use synthetic records for demonstrations where appropriate, and do not commit passwords, secret keys, or other sensitive information to GitHub.

## 🔐 Safety and Reliability

The official problem statement emphasizes the following practices:

- Validate donation details before processing.
- Evaluate the food-safety window and NGO capacity using available evidence.
- Require human approval before consequential actions.
- Prevent duplicate pickup requests when retrying operations.
- Keep pending and failed actions visible.
- Verify NGO acceptance before reporting collection.
- Require restaurant reconfirmation when the drop-off location changes.
- Use mock or synthetic data for demonstrations involving sensitive information.
- Never bypass OTP or CAPTCHA protections.

These are the required safety considerations; document each as implemented only after verifying the corresponding behavior.

## 📸 Demo and Submission Evidence

The hackathon submission requires a deployed working agent, source evidence, a presentation, and test cases.

- **Live Demo:** Add the deployed website URL.
- **Demo Video:** Add the 2–3 minute demonstration video URL.
- **GitHub Repository:** Add this repository URL.
- **Source Code:** Provide a publicly accessible source link.
- **Architecture:** Add the architecture diagram or document.
- **Presentation:** Add the presentation URL.
- **Test Evidence:** Include inputs, actual results, and screenshots or records for TC1–TC4.
- **LinkedIn Evidence:** Add the relevant post link and required screenshot to the official submission form.

Do not list a demo URL or test as completed until it is available and verified.

## 🌱 Social Impact

Surplus Donation aims to:

- Reduce avoidable food waste.
- Improve coordination between restaurants and NGOs.
- Support responsible redistribution of surplus food.
- Improve visibility into donation and pickup status.
- Encourage safer, more transparent donation workflows.

## 🏆 Hackathon Information

**Event:** Ziro.Digital Agentic AI Hackathon 2026  
**Category:** Industry / Social Impact & Sustainability AI  
**Assigned Challenge:** Surplus Food Donation Matcher

The challenge focuses on collecting donation details, evaluating food safety and NGO capacity, proposing a match, obtaining human approval, creating a pickup request, and verifying the pickup status.

## 👩‍💻 Author

**Lohitha Sri Mallarapu**  
Solo Participant — Ziro.Digital Agentic AI Hackathon 2026

---

**Surplus Donation — Turning surplus into meaningful meals. 💚**
