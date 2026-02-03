from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, Response, stream_with_context
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import db, Movie, Episode, User, Transaction, SubscriptionPlan, SiteSettings
from app.decorators import admin_required
from datetime import datetime, timedelta
from sqlalchemy import func
import os
import requests
import urllib3

# Suppress InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

admin_bp = Blueprint('admin', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'ico'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    total_users = User.query.count()
    total_movies = Movie.query.count()
    total_transactions = Transaction.query.count()
    total_omset = db.session.query(func.sum(Transaction.amount)).filter(Transaction.status == 'paid').scalar() or 0
    return render_template('admin/dashboard.html', total_users=total_users, total_movies=total_movies, total_transactions=total_transactions, total_omset=total_omset)

@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    settings = SiteSettings.query.first()
    if not settings:
        settings = SiteSettings(site_title="DracinLovers")
        db.session.add(settings)
        db.session.commit()
    
    if request.method == 'POST':
        settings.site_title = request.form.get('site_title')
        settings.site_description = request.form.get('site_description')
        settings.meta_keywords = request.form.get('meta_keywords')
        settings.google_analytics_id = request.form.get('google_analytics_id')
        settings.google_search_console_id = request.form.get('google_search_console_id')
        
        # Handle File Uploads
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'assets')
        os.makedirs(upload_folder, exist_ok=True)

        if 'favicon' in request.files:
            file = request.files['favicon']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"favicon_{int(datetime.utcnow().timestamp())}_{file.filename}")
                file.save(os.path.join(upload_folder, filename))
                settings.favicon_url = url_for('static', filename=f'uploads/assets/{filename}')
        
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"logo_{int(datetime.utcnow().timestamp())}_{file.filename}")
                file.save(os.path.join(upload_folder, filename))
                settings.logo_url = url_for('static', filename=f'uploads/assets/{filename}')
        
        db.session.commit()
        flash('Site settings updated successfully', 'success')
        return redirect(url_for('admin.settings'))
        
    return render_template('admin/settings.html', settings=settings)

# --- Movies CRUD ---

@admin_bp.route('/movies')
@login_required
@admin_required
def movies():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '')
    
    query = Movie.query
    if search_query:
        query = query.filter(Movie.title.ilike(f'%{search_query}%'))
        
    movies = query.order_by(Movie.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/movies.html', movies=movies, search_query=search_query)

@admin_bp.route('/movies/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_movie():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        poster_url = request.form.get('poster_url')
        
        movie = Movie(title=title, description=description, poster_url=poster_url)
        db.session.add(movie)
        db.session.commit()
        flash('Movie added successfully', 'success')
        return redirect(url_for('admin.movies'))
    return render_template('admin/movie_form.html')

@admin_bp.route('/movies/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_movie(id):
    movie = Movie.query.get_or_404(id)
    if request.method == 'POST':
        movie.title = request.form.get('title')
        movie.description = request.form.get('description')
        movie.poster_url = request.form.get('poster_url')
        
        db.session.commit()
        flash('Movie updated successfully', 'success')
        return redirect(url_for('admin.movies'))
    return render_template('admin/movie_form.html', movie=movie)

@admin_bp.route('/movies/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_movie(id):
    movie = Movie.query.get_or_404(id)
    # Delete associated episodes first or let cascade handle it if configured (not configured in models, so manual delete)
    Episode.query.filter_by(movie_id=id).delete()
    db.session.delete(movie)
    db.session.commit()
    flash('Movie deleted successfully', 'success')
    return redirect(url_for('admin.movies'))

# --- Episodes CRUD ---

@admin_bp.route('/movies/<int:movie_id>/episodes')
@login_required
@admin_required
def movie_episodes(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    episodes = Episode.query.filter_by(movie_id=movie_id).order_by(Episode.episode_number.asc()).all()
    return render_template('admin/episodes.html', movie=movie, episodes=episodes)

@admin_bp.route('/movies/<int:movie_id>/episodes/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_episode(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    if request.method == 'POST':
        title = request.form.get('title')
        episode_number = request.form.get('episode_number')
        video_url = request.form.get('video_url')
        is_free = request.form.get('is_free') == 'on'
        
        episode = Episode(
            movie_id=movie_id,
            title=title,
            episode_number=episode_number,
            video_url=video_url,
            is_free=is_free
        )
        db.session.add(episode)
        db.session.commit()
        flash('Episode added successfully', 'success')
        return redirect(url_for('admin.movie_episodes', movie_id=movie_id))
    return render_template('admin/episode_form.html', movie=movie)

@admin_bp.route('/episodes/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_episode(id):
    episode = Episode.query.get_or_404(id)
    if request.method == 'POST':
        episode.title = request.form.get('title')
        episode.episode_number = request.form.get('episode_number')
        episode.video_url = request.form.get('video_url')
        episode.is_free = request.form.get('is_free') == 'on'
        
        db.session.commit()
        flash('Episode updated successfully', 'success')
        return redirect(url_for('admin.movie_episodes', movie_id=episode.movie_id))
    return render_template('admin/episode_form.html', episode=episode, movie=episode.movie)

@admin_bp.route('/episodes/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_episode(id):
    episode = Episode.query.get_or_404(id)
    movie_id = episode.movie_id
    db.session.delete(episode)
    db.session.commit()
    flash('Episode deleted successfully', 'success')
    return redirect(url_for('admin.movie_episodes', movie_id=movie_id))

@admin_bp.route('/episodes/download/<int:id>')
@login_required
@admin_required
def download_episode(id):
    episode = Episode.query.get_or_404(id)
    url = episode.video_url
    
    if not url:
        flash('No video URL found for this episode', 'error')
        return redirect(url_for('admin.movie_episodes', movie_id=episode.movie_id))
    
    # Headers required by the upstream server
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:146.0) Gecko/20100101 Firefox/146.0",
        "Accept": "video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5",
        "Accept-Language": "en-CA,en-US;q=0.7,en;q=0.3",
        "Origin": "https://www.dracinlovers.com",
        "Referer": "https://www.dracinlovers.com/",
        "Sec-Fetch-Dest": "video",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
        "Priority": "u=4",
        "Te": "trailers"
    }
    
    try:
        req = requests.get(url, headers=headers, stream=True, verify=False)
        
        # Determine filename
        ext = 'mp4' # Default
        if '.' in url.split('/')[-1]:
            ext = url.split('/')[-1].split('.')[-1].split('?')[0]
            
        safe_title = secure_filename(f"{episode.movie.title} - EP{episode.episode_number}")
        filename = f"{safe_title}.{ext}"

        # Exclude some headers
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        resp_headers = [(name, value) for (name, value) in req.headers.items()
                       if name.lower() not in excluded_headers]
        
        # Add Content-Disposition to force download
        resp_headers.append(('Content-Disposition', f'attachment; filename="{filename}"'))
        
        if 'Content-Length' in req.headers:
            resp_headers.append(('Content-Length', req.headers['Content-Length']))
            
        return Response(stream_with_context(req.iter_content(chunk_size=1024*16)), 
                       status=req.status_code, 
                       headers=resp_headers)
                       
    except requests.exceptions.RequestException as e:
        flash(f"Error fetching URL: {str(e)}", 'error')
        return redirect(url_for('admin.movie_episodes', movie_id=episode.movie_id))

# --- Plans CRUD ---

@admin_bp.route('/plans')
@login_required
@admin_required
def plans():
    plans = SubscriptionPlan.query.all()
    return render_template('admin/plans.html', plans=plans)

@admin_bp.route('/plans/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_plan():
    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        duration_days = request.form.get('duration_days')
        is_active = request.form.get('is_active') == 'on'
        
        plan = SubscriptionPlan(name=name, price=price, duration_days=duration_days, is_active=is_active)
        db.session.add(plan)
        db.session.commit()
        flash('Plan added successfully', 'success')
        return redirect(url_for('admin.plans'))
    return render_template('admin/plan_form.html')

@admin_bp.route('/plans/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_plan(id):
    plan = SubscriptionPlan.query.get_or_404(id)
    if request.method == 'POST':
        plan.name = request.form.get('name')
        plan.price = request.form.get('price')
        plan.duration_days = request.form.get('duration_days')
        plan.is_active = request.form.get('is_active') == 'on'
        
        db.session.commit()
        flash('Plan updated successfully', 'success')
        return redirect(url_for('admin.plans'))
    return render_template('admin/plan_form.html', plan=plan)

@admin_bp.route('/plans/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_plan(id):
    plan = SubscriptionPlan.query.get_or_404(id)
    db.session.delete(plan)
    db.session.commit()
    flash('Plan deleted successfully', 'success')
    return redirect(url_for('admin.plans'))


# --- Users & Transactions ---

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/users.html', users=users)

@admin_bp.route('/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(id):
    user = User.query.get_or_404(id)
    if request.method == 'POST':
        user.role = request.form.get('role')
        # Optional: Allow editing other fields if needed, but priority is role
        
        db.session.commit()
        flash('User updated successfully', 'success')
        return redirect(url_for('admin.users'))
    return render_template('admin/user_form.html', user=user)

@admin_bp.route('/transactions')
@login_required
@admin_required
def transactions():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    
    query = Transaction.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
        
    transactions = query.order_by(Transaction.created_at.desc()).paginate(page=page, per_page=20)
    
    return render_template('admin/transactions.html', transactions=transactions, status_filter=status_filter)

@admin_bp.route('/transaction/<int:id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_transaction(id):
    transaction = Transaction.query.get_or_404(id)
    if transaction.status == 'pending':
        transaction.status = 'paid'
        
        # Update user subscription logic
        if transaction.plan_id:
            plan = SubscriptionPlan.query.get(transaction.plan_id)
            if plan:
                user = User.query.get(transaction.user_id)
                current_expiry = user.subscription_end_date or datetime.utcnow()
                # Ensure we don't start from the past if expired long ago
                if current_expiry < datetime.utcnow():
                    current_expiry = datetime.utcnow()
                
                try:
                    user.subscription_end_date = current_expiry + timedelta(days=plan.duration_days)
                except OverflowError:
                    # Cap at a reasonable max date (e.g., year 9999)
                    user.subscription_end_date = datetime(9999, 12, 31, 23, 59, 59)
            
        db.session.commit()
        flash('Transaction approved', 'success')
    return redirect(url_for('admin.transactions'))
