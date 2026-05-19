"""
Agile Sprint Tracker Dashboard
===============================
A comprehensive sprint management tool with burndown charts, velocity tracking,
sprint planning, user story management, and team performance analytics.

Tech Stack: Flask + SQLAlchemy + Chart.js + Jinja2
Author: Saanvi (Tech PM Portfolio)
"""

import os
import json
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import statistics

# ─── App Configuration ────────────────────────────────────────────────────────

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///sprint_tracker.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ─── Models ───────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='developer')  # scrum_master, product_owner, developer
    avatar_color = db.Column(db.String(7), default='#6366f1')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sprints = db.relationship('Sprint', backref='project', lazy=True, cascade='all, delete-orphan')
    stories = db.relationship('UserStory', backref='project', lazy=True, cascade='all, delete-orphan')


class Sprint(db.Model):
    __tablename__ = 'sprints'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    goal = db.Column(db.Text)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='planning')  # planning, active, completed
    capacity_points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    stories = db.relationship('UserStory', backref='sprint', lazy=True)
    burndown_entries = db.relationship('BurndownEntry', backref='sprint', lazy=True, cascade='all, delete-orphan')
    retrospective = db.relationship('Retrospective', backref='sprint', uselist=False, cascade='all, delete-orphan')

    @property
    def total_points(self):
        return sum(s.story_points for s in self.stories if s.story_points)

    @property
    def completed_points(self):
        return sum(s.story_points for s in self.stories if s.status == 'done' and s.story_points)

    @property
    def velocity(self):
        if self.status == 'completed':
            return self.completed_points
        return 0

    @property
    def progress_percentage(self):
        total = self.total_points
        if total == 0:
            return 0
        return round((self.completed_points / total) * 100)

    @property
    def days_remaining(self):
        if self.status == 'completed':
            return 0
        delta = self.end_date - datetime.utcnow().date()
        return max(0, delta.days)

    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days


class UserStory(db.Model):
    __tablename__ = 'user_stories'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    sprint_id = db.Column(db.Integer, db.ForeignKey('sprints.id'), nullable=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    acceptance_criteria = db.Column(db.Text)
    story_points = db.Column(db.Integer, default=0)
    priority = db.Column(db.String(20), default='medium')  # critical, high, medium, low
    status = db.Column(db.String(20), default='backlog')  # backlog, todo, in_progress, review, done
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    epic = db.Column(db.String(100))
    labels = db.Column(db.String(300))  # comma-separated
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    assignee = db.relationship('User', foreign_keys=[assigned_to])

    @property
    def cycle_time(self):
        """Days from in_progress to done"""
        if self.completed_at and self.created_at:
            return (self.completed_at - self.created_at).days
        return None


class BurndownEntry(db.Model):
    __tablename__ = 'burndown_entries'
    id = db.Column(db.Integer, primary_key=True)
    sprint_id = db.Column(db.Integer, db.ForeignKey('sprints.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    remaining_points = db.Column(db.Integer, nullable=False)
    completed_points = db.Column(db.Integer, default=0)
    added_points = db.Column(db.Integer, default=0)  # scope creep tracking


class Retrospective(db.Model):
    __tablename__ = 'retrospectives'
    id = db.Column(db.Integer, primary_key=True)
    sprint_id = db.Column(db.Integer, db.ForeignKey('sprints.id'), nullable=False)
    went_well = db.Column(db.Text)
    to_improve = db.Column(db.Text)
    action_items = db.Column(db.Text)
    team_morale = db.Column(db.Integer, default=3)  # 1-5 scale
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    action = db.Column(db.String(200), nullable=False)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User')


# ─── Auth ─────────────────────────────────────────────────────────────────────

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role', 'developer')

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('register'))

        user = User(username=username, email=email, role=role)
        user.set_password(password)
        colors = ['#6366f1', '#ec4899', '#14b8a6', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']
        user.avatar_color = colors[len(User.query.all()) % len(colors)]
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Account created successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'error')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ─── Dashboard ────────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def dashboard():
    projects = Project.query.all()
    active_sprints = Sprint.query.filter_by(status='active').all()
    recent_activity = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(15).all()

    # Velocity data across completed sprints
    completed_sprints = Sprint.query.filter_by(status='completed').order_by(Sprint.end_date).all()
    velocity_data = {
        'labels': [s.name for s in completed_sprints[-8:]],
        'values': [s.velocity for s in completed_sprints[-8:]],
    }
    if velocity_data['values']:
        velocity_data['average'] = round(statistics.mean(velocity_data['values']), 1)
        velocity_data['trend'] = 'up' if len(velocity_data['values']) > 1 and velocity_data['values'][-1] > velocity_data['average'] else 'down'
    else:
        velocity_data['average'] = 0
        velocity_data['trend'] = 'neutral'

    # Story status distribution
    all_stories = UserStory.query.all()
    status_dist = {}
    for s in all_stories:
        status_dist[s.status] = status_dist.get(s.status, 0) + 1

    # Team workload
    team_members = User.query.all()
    workload = []
    for member in team_members:
        assigned = UserStory.query.filter_by(assigned_to=member.id).filter(
            UserStory.status.in_(['todo', 'in_progress', 'review'])
        ).all()
        workload.append({
            'user': member,
            'points': sum(s.story_points for s in assigned if s.story_points),
            'count': len(assigned)
        })

    return render_template('dashboard.html',
                           projects=projects,
                           active_sprints=active_sprints,
                           recent_activity=recent_activity,
                           velocity_data=velocity_data,
                           status_dist=status_dist,
                           workload=workload)


# ─── Project CRUD ─────────────────────────────────────────────────────────────

@app.route('/project/new', methods=['GET', 'POST'])
@login_required
def new_project():
    if request.method == 'POST':
        project = Project(
            name=request.form['name'],
            description=request.form.get('description', ''),
            created_by=current_user.id
        )
        db.session.add(project)
        db.session.commit()
        log_activity(project.id, f'Created project "{project.name}"', 'project', project.id)
        flash('Project created!', 'success')
        return redirect(url_for('project_board', project_id=project.id))
    return render_template('new_project.html')


@app.route('/project/<int:project_id>')
@login_required
def project_board(project_id):
    project = Project.query.get_or_404(project_id)
    active_sprint = Sprint.query.filter_by(project_id=project_id, status='active').first()
    backlog = UserStory.query.filter_by(project_id=project_id, sprint_id=None).order_by(UserStory.priority).all()
    team = User.query.all()

    # Kanban columns for active sprint
    columns = {}
    if active_sprint:
        for status in ['todo', 'in_progress', 'review', 'done']:
            columns[status] = UserStory.query.filter_by(
                sprint_id=active_sprint.id, status=status
            ).order_by(UserStory.priority).all()

    return render_template('project_board.html',
                           project=project,
                           active_sprint=active_sprint,
                           backlog=backlog,
                           columns=columns,
                           team=team)


# ─── Sprint Management ───────────────────────────────────────────────────────

@app.route('/project/<int:project_id>/sprint/new', methods=['GET', 'POST'])
@login_required
def new_sprint(project_id):
    project = Project.query.get_or_404(project_id)
    if request.method == 'POST':
        sprint = Sprint(
            project_id=project_id,
            name=request.form['name'],
            goal=request.form.get('goal', ''),
            start_date=datetime.strptime(request.form['start_date'], '%Y-%m-%d').date(),
            end_date=datetime.strptime(request.form['end_date'], '%Y-%m-%d').date(),
            capacity_points=int(request.form.get('capacity_points', 0))
        )
        db.session.add(sprint)
        db.session.commit()
        log_activity(project_id, f'Created sprint "{sprint.name}"', 'sprint', sprint.id)
        flash('Sprint created!', 'success')
        return redirect(url_for('sprint_detail', sprint_id=sprint.id))
    return render_template('new_sprint.html', project=project)


@app.route('/sprint/<int:sprint_id>')
@login_required
def sprint_detail(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    stories = UserStory.query.filter_by(sprint_id=sprint_id).all()

    # Generate burndown data
    burndown = generate_burndown_data(sprint)

    # Story breakdown by status
    status_counts = {}
    for s in stories:
        status_counts[s.status] = status_counts.get(s.status, 0) + 1

    # Scope creep detection
    original_points = sprint.capacity_points
    current_points = sprint.total_points
    scope_creep = current_points - original_points if original_points > 0 else 0

    # Cycle time stats
    cycle_times = [s.cycle_time for s in stories if s.cycle_time is not None]
    avg_cycle_time = round(statistics.mean(cycle_times), 1) if cycle_times else 0

    return render_template('sprint_detail.html',
                           sprint=sprint,
                           stories=stories,
                           burndown=burndown,
                           status_counts=status_counts,
                           scope_creep=scope_creep,
                           avg_cycle_time=avg_cycle_time)


@app.route('/sprint/<int:sprint_id>/start', methods=['POST'])
@login_required
def start_sprint(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    sprint.status = 'active'
    # Initialize burndown
    entry = BurndownEntry(
        sprint_id=sprint.id,
        date=sprint.start_date,
        remaining_points=sprint.total_points,
        completed_points=0
    )
    db.session.add(entry)
    db.session.commit()
    log_activity(sprint.project_id, f'Started sprint "{sprint.name}"', 'sprint', sprint.id)
    flash('Sprint started!', 'success')
    return redirect(url_for('sprint_detail', sprint_id=sprint.id))


@app.route('/sprint/<int:sprint_id>/complete', methods=['POST'])
@login_required
def complete_sprint(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    sprint.status = 'completed'
    # Move incomplete stories back to backlog
    incomplete = UserStory.query.filter(
        UserStory.sprint_id == sprint_id,
        UserStory.status != 'done'
    ).all()
    for story in incomplete:
        story.sprint_id = None
        story.status = 'backlog'
    db.session.commit()
    log_activity(sprint.project_id, f'Completed sprint "{sprint.name}" — velocity: {sprint.velocity}', 'sprint', sprint.id)
    flash(f'Sprint completed! Velocity: {sprint.velocity} points. {len(incomplete)} stories moved to backlog.', 'success')
    return redirect(url_for('sprint_detail', sprint_id=sprint.id))


# ─── User Story CRUD ─────────────────────────────────────────────────────────

@app.route('/project/<int:project_id>/story/new', methods=['GET', 'POST'])
@login_required
def new_story(project_id):
    project = Project.query.get_or_404(project_id)
    if request.method == 'POST':
        story = UserStory(
            project_id=project_id,
            sprint_id=request.form.get('sprint_id') or None,
            title=request.form['title'],
            description=request.form.get('description', ''),
            acceptance_criteria=request.form.get('acceptance_criteria', ''),
            story_points=int(request.form.get('story_points', 0)),
            priority=request.form.get('priority', 'medium'),
            assigned_to=request.form.get('assigned_to') or None,
            epic=request.form.get('epic', ''),
            labels=request.form.get('labels', '')
        )
        db.session.add(story)
        db.session.commit()
        log_activity(project_id, f'Created story "{story.title}"', 'story', story.id)
        flash('User story created!', 'success')
        return redirect(url_for('project_board', project_id=project_id))
    sprints = Sprint.query.filter_by(project_id=project_id).filter(Sprint.status != 'completed').all()
    team = User.query.all()
    return render_template('new_story.html', project=project, sprints=sprints, team=team)


@app.route('/story/<int:story_id>/update_status', methods=['POST'])
@login_required
def update_story_status(story_id):
    story = UserStory.query.get_or_404(story_id)
    new_status = request.form.get('status') or request.json.get('status')
    old_status = story.status
    story.status = new_status

    if new_status == 'done' and old_status != 'done':
        story.completed_at = datetime.utcnow()
        # Update burndown
        if story.sprint_id:
            update_burndown(story.sprint_id)

    db.session.commit()
    log_activity(story.project_id, f'Moved "{story.title}" from {old_status} → {new_status}', 'story', story.id)

    if request.is_json:
        return jsonify({'success': True})
    flash('Story updated!', 'success')
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/story/<int:story_id>/assign', methods=['POST'])
@login_required
def assign_story(story_id):
    story = UserStory.query.get_or_404(story_id)
    story.assigned_to = request.form.get('assigned_to') or None
    db.session.commit()
    return jsonify({'success': True})


@app.route('/story/<int:story_id>/move_to_sprint', methods=['POST'])
@login_required
def move_to_sprint(story_id):
    story = UserStory.query.get_or_404(story_id)
    sprint_id = request.form.get('sprint_id') or request.json.get('sprint_id')
    story.sprint_id = sprint_id
    if sprint_id:
        story.status = 'todo'
    db.session.commit()
    log_activity(story.project_id, f'Moved "{story.title}" to sprint', 'story', story.id)
    if request.is_json:
        return jsonify({'success': True})
    return redirect(request.referrer or url_for('dashboard'))


# ─── Analytics ────────────────────────────────────────────────────────────────

@app.route('/analytics')
@login_required
def analytics():
    projects = Project.query.all()
    completed_sprints = Sprint.query.filter_by(status='completed').order_by(Sprint.end_date).all()

    # Velocity trend
    velocity_trend = [{'name': s.name, 'velocity': s.velocity, 'capacity': s.capacity_points} for s in completed_sprints]

    # Cumulative flow data
    all_stories = UserStory.query.order_by(UserStory.created_at).all()

    # Lead time distribution
    lead_times = []
    for story in all_stories:
        if story.completed_at:
            lt = (story.completed_at - story.created_at).days
            lead_times.append(lt)

    lead_time_stats = {}
    if lead_times:
        lead_time_stats = {
            'average': round(statistics.mean(lead_times), 1),
            'median': round(statistics.median(lead_times), 1),
            'p85': round(sorted(lead_times)[int(len(lead_times) * 0.85)], 1) if len(lead_times) > 1 else lead_times[0],
            'distribution': lead_times
        }

    # Points by epic
    epic_data = {}
    for story in all_stories:
        epic = story.epic or 'No Epic'
        if epic not in epic_data:
            epic_data[epic] = {'total': 0, 'done': 0}
        epic_data[epic]['total'] += story.story_points or 0
        if story.status == 'done':
            epic_data[epic]['done'] += story.story_points or 0

    # Team velocity contribution
    team_contribution = {}
    for story in all_stories:
        if story.status == 'done' and story.assigned_to:
            user = User.query.get(story.assigned_to)
            if user:
                name = user.username
                team_contribution[name] = team_contribution.get(name, 0) + (story.story_points or 0)

    return render_template('analytics.html',
                           velocity_trend=velocity_trend,
                           lead_time_stats=lead_time_stats,
                           epic_data=epic_data,
                           team_contribution=team_contribution)


# ─── Retrospective ───────────────────────────────────────────────────────────

@app.route('/sprint/<int:sprint_id>/retro', methods=['GET', 'POST'])
@login_required
def retrospective(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    if request.method == 'POST':
        retro = Retrospective.query.filter_by(sprint_id=sprint_id).first()
        if not retro:
            retro = Retrospective(sprint_id=sprint_id)
            db.session.add(retro)
        retro.went_well = request.form.get('went_well', '')
        retro.to_improve = request.form.get('to_improve', '')
        retro.action_items = request.form.get('action_items', '')
        retro.team_morale = int(request.form.get('team_morale', 3))
        db.session.commit()
        flash('Retrospective saved!', 'success')
        return redirect(url_for('sprint_detail', sprint_id=sprint_id))
    retro = Retrospective.query.filter_by(sprint_id=sprint_id).first()
    return render_template('retrospective.html', sprint=sprint, retro=retro)


# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.route('/api/burndown/<int:sprint_id>')
@login_required
def api_burndown(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    data = generate_burndown_data(sprint)
    return jsonify(data)


@app.route('/api/velocity')
@login_required
def api_velocity():
    completed = Sprint.query.filter_by(status='completed').order_by(Sprint.end_date).all()
    return jsonify({
        'labels': [s.name for s in completed],
        'velocity': [s.velocity for s in completed],
        'capacity': [s.capacity_points for s in completed]
    })


# ─── Helper Functions ─────────────────────────────────────────────────────────

def generate_burndown_data(sprint):
    """Generate ideal and actual burndown data for a sprint"""
    total_points = sprint.total_points
    duration = sprint.duration_days

    # Ideal burndown line
    ideal = []
    for i in range(duration + 1):
        day = sprint.start_date + timedelta(days=i)
        remaining = total_points - (total_points * i / duration) if duration > 0 else 0
        ideal.append({'date': day.isoformat(), 'points': round(remaining, 1)})

    # Actual burndown from entries
    entries = BurndownEntry.query.filter_by(sprint_id=sprint.id).order_by(BurndownEntry.date).all()
    actual = [{'date': e.date.isoformat(), 'points': e.remaining_points} for e in entries]

    # If no entries, compute from story statuses
    if not actual and sprint.status in ('active', 'completed'):
        done_stories = UserStory.query.filter_by(sprint_id=sprint.id, status='done').all()
        remaining = total_points - sum(s.story_points for s in done_stories if s.story_points)
        actual = [{'date': datetime.utcnow().date().isoformat(), 'points': remaining}]

    return {
        'ideal': ideal,
        'actual': actual,
        'total_points': total_points,
        'labels': [d['date'] for d in ideal]
    }


def update_burndown(sprint_id):
    """Update burndown entry for today"""
    sprint = Sprint.query.get(sprint_id)
    if not sprint:
        return
    today = datetime.utcnow().date()
    done_points = sum(s.story_points for s in sprint.stories if s.status == 'done' and s.story_points)
    remaining = sprint.total_points - done_points

    entry = BurndownEntry.query.filter_by(sprint_id=sprint_id, date=today).first()
    if entry:
        entry.remaining_points = remaining
        entry.completed_points = done_points
    else:
        entry = BurndownEntry(
            sprint_id=sprint_id,
            date=today,
            remaining_points=remaining,
            completed_points=done_points
        )
        db.session.add(entry)
    db.session.commit()


def log_activity(project_id, action, entity_type=None, entity_id=None):
    log = ActivityLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        project_id=project_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id
    )
    db.session.add(log)
    db.session.commit()


# ─── Template Filters ─────────────────────────────────────────────────────────

@app.template_filter('timeago')
def timeago_filter(dt):
    if not dt:
        return ''
    now = datetime.utcnow()
    diff = now - dt
    if diff.days > 30:
        return dt.strftime('%b %d, %Y')
    elif diff.days > 0:
        return f'{diff.days}d ago'
    elif diff.seconds > 3600:
        return f'{diff.seconds // 3600}h ago'
    elif diff.seconds > 60:
        return f'{diff.seconds // 60}m ago'
    return 'just now'


@app.template_filter('priority_color')
def priority_color_filter(priority):
    colors = {
        'critical': '#ef4444',
        'high': '#f59e0b',
        'medium': '#6366f1',
        'low': '#94a3b8'
    }
    return colors.get(priority, '#94a3b8')


# ─── Seed Data ────────────────────────────────────────────────────────────────

def seed_demo_data():
    """Populate database with realistic demo data"""
    if User.query.first():
        return

    # Users
    users_data = [
        ('saanvi', 'saanvi@example.com', 'password123', 'scrum_master', '#6366f1'),
        ('stefanie', 'stefanie@example.com', 'password123', 'developer', '#ec4899'),
        ('alex', 'alex@example.com', 'password123', 'developer', '#14b8a6'),
        ('jordan', 'jordan@example.com', 'password123', 'product_owner', '#f59e0b'),
    ]
    users = []
    for uname, email, pwd, role, color in users_data:
        u = User(username=uname, email=email, role=role, avatar_color=color)
        u.set_password(pwd)
        db.session.add(u)
        users.append(u)
    db.session.flush()

    # Project
    project = Project(name='Manzanita Health Platform', description='Telehealth web application with live chat, messaging, and video calls', created_by=users[0].id)
    db.session.add(project)
    db.session.flush()

    # Completed sprints with history
    sprint_data = [
        ('Sprint 1 — Foundation', -42, -29, 'completed', 30),
        ('Sprint 2 — Core Features', -28, -15, 'completed', 35),
        ('Sprint 3 — Integration', -14, -1, 'completed', 40),
        ('Sprint 4 — Polish & Launch', 0, 13, 'active', 38),
    ]

    for sname, start_offset, end_offset, status, capacity in sprint_data:
        sprint = Sprint(
            project_id=project.id,
            name=sname,
            goal=f'Goal for {sname}',
            start_date=datetime.utcnow().date() + timedelta(days=start_offset),
            end_date=datetime.utcnow().date() + timedelta(days=end_offset),
            status=status,
            capacity_points=capacity
        )
        db.session.add(sprint)
        db.session.flush()

        # Stories for each sprint
        story_templates = [
            ('User authentication system', 'Implement login/register with OAuth', 8, 'critical', 'Auth'),
            ('Patient dashboard', 'Display appointments and health records', 5, 'high', 'Dashboard'),
            ('Live chat feature', 'Real-time messaging between patient and provider', 8, 'high', 'Communication'),
            ('Appointment scheduling', 'Calendar-based booking system', 5, 'medium', 'Scheduling'),
            ('Search functionality', 'Full-text search across the platform', 3, 'medium', 'Search'),
            ('Notification system', 'Email and in-app notifications', 5, 'low', 'Notifications'),
        ]

        for i, (title, desc, points, priority, epic) in enumerate(story_templates):
            story_status = 'done' if status == 'completed' else ['todo', 'in_progress', 'review', 'done', 'todo', 'in_progress'][i]
            story = UserStory(
                project_id=project.id,
                sprint_id=sprint.id,
                title=f'{title} ({sname.split(" — ")[0]})',
                description=desc,
                acceptance_criteria=f'- Feature works as expected\n- Unit tests pass\n- Code reviewed',
                story_points=points,
                priority=priority,
                status=story_status,
                assigned_to=users[i % len(users)].id,
                epic=epic,
                labels='frontend,backend' if i % 2 == 0 else 'backend,api',
                completed_at=datetime.utcnow() - timedelta(days=max(0, -end_offset)) if story_status == 'done' else None
            )
            db.session.add(story)

        # Burndown entries for completed sprints
        if status == 'completed':
            total = sum(s[2] for s in story_templates)
            for day in range(15):
                remaining = max(0, total - (total * day / 14) + (2 if day == 7 else 0))
                entry = BurndownEntry(
                    sprint_id=sprint.id,
                    date=sprint.start_date + timedelta(days=day),
                    remaining_points=round(remaining),
                    completed_points=total - round(remaining)
                )
                db.session.add(entry)

    # Backlog stories
    backlog_stories = [
        ('Video call optimization', 'Improve WebRTC connection quality', 8, 'high', 'Communication'),
        ('Data export feature', 'Export patient data as CSV/PDF', 3, 'medium', 'Data'),
        ('Admin analytics dashboard', 'Usage stats and KPIs for admins', 5, 'medium', 'Dashboard'),
        ('Multi-language support', 'i18n for Hindi, Gujarati, Bengali', 8, 'low', 'i18n'),
        ('Accessibility audit', 'WCAG 2.1 AA compliance', 5, 'high', 'Quality'),
    ]
    for title, desc, points, priority, epic in backlog_stories:
        story = UserStory(
            project_id=project.id,
            title=title,
            description=desc,
            story_points=points,
            priority=priority,
            epic=epic
        )
        db.session.add(story)

    db.session.commit()
    print("✅ Demo data seeded successfully!")


# ─── App Startup ──────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()
    seed_demo_data()


if __name__ == '__main__':
    app.run(debug=True, port=5001)
