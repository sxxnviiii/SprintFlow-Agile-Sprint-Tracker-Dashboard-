# 🚀 SprintFlow — Agile Sprint Tracker Dashboard

A full-stack sprint management tool with burndown charts, velocity tracking, Kanban boards, and team analytics.

## Features
- **Sprint Planning**: Create sprints with goals, capacity, and date ranges
- **Kanban Board**: Drag-and-drop user stories across status columns
- **Burndown Charts**: Ideal vs actual burndown with scope creep detection
- **Velocity Tracking**: Historical velocity trend across sprints
- **Analytics Dashboard**: Lead time distribution, epic breakdown, team contribution
- **Retrospectives**: Went well / To improve / Action items with team morale
- **Multi-user Auth**: Role-based (Scrum Master, PO, Developer)
- **Activity Feed**: Real-time project activity log

## Tech Stack
- **Backend**: Python / Flask / SQLAlchemy / Flask-Login
- **Frontend**: Jinja2 / Chart.js / Vanilla JS (drag-and-drop)
- **Database**: SQLite (swap to PostgreSQL for production)

## Quick Start
```bash
pip install -r requirements.txt
python app.py
```
Open `http://localhost:5001` — Demo login: `saanvi` / `password123`

## Architecture
```
01-sprint-tracker/
├── app.py              # Flask app, models, routes, seed data
├── requirements.txt
├── templates/
│   ├── base.html           # Layout + sidebar + CSS
│   ├── dashboard.html      # Metrics, velocity chart, activity
│   ├── project_board.html  # Kanban + backlog table
│   ├── sprint_detail.html  # Burndown chart + stories table
│   ├── analytics.html      # Velocity, lead time, epic, team charts
│   ├── retrospective.html  # Retro form with morale rating
│   ├── new_project.html
│   ├── new_sprint.html
│   ├── new_story.html
│   ├── login.html
│   └── register.html
└── README.md
```
