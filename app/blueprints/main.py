from flask import Blueprint, render_template, request, abort, Response, stream_with_context, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db, cache
from app.models import Movie, Episode, SubscriptionPlan, Favorite, SiteSettings, Transaction
from sqlalchemy.orm import subqueryload
from datetime import datetime, timedelta
import requests
import urllib3
from flask import make_response

# Suppress InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

main_bp = Blueprint('main', __name__)

@main_bp.context_processor
def inject_settings():
    settings = SiteSettings.query.first()
    return dict(site_settings=settings)

@main_bp.route('/robots.txt')
def robots():
    response = make_response(render_template('main/robots.txt'))
    response.headers["Content-Type"] = "text/plain"
    return response

@main_bp.route('/sitemap.xml')
def sitemap():
    movies = Movie.query.all()
    response = make_response(render_template('main/sitemap.xml', movies=movies, base_url=request.url_root.rstrip('/'), now=datetime.utcnow()))
    response.headers["Content-Type"] = "application/xml"
    return response

@main_bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    movies = Movie.query.order_by(Movie.created_at.desc()).paginate(page=page, per_page=12)
    
    # Get user favorites if logged in
    user_favorites = []
    if current_user.is_authenticated:
        user_favorites = [fav.movie_id for fav in Favorite.query.filter_by(user_id=current_user.id).all()]
        
    return render_template('main/index.html', movies=movies, user_favorites=user_favorites)

@main_bp.route('/search')
def search():
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    
    if query:
        # Optimasi N+1 dengan subqueryload
        movies = Movie.query.options(subqueryload(Movie.episodes)).filter(Movie.title.ilike(f'%{query}%')).order_by(Movie.created_at.desc()).paginate(page=page, per_page=12)
    else:
        movies = None
        
    return render_template('main/search.html', movies=movies, query=query)

@main_bp.route('/profile')
@login_required
def profile():
    plans = SubscriptionPlan.query.filter_by(is_active=True).order_by(SubscriptionPlan.price).all()
    return render_template('main/profile.html', now=datetime.utcnow(), plans=plans)

@main_bp.route('/history')
@login_required
def history():
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.created_at.desc()).all()
    return render_template('main/history.html', transactions=transactions)

@main_bp.route('/favorites')
@login_required
def favorites():
    page = request.args.get('page', 1, type=int)
    favorites = Favorite.query.filter_by(user_id=current_user.id).order_by(Favorite.created_at.desc()).paginate(page=page, per_page=12)
    
    # Get movies from favorites
    movie_ids = [fav.movie_id for fav in favorites.items]
    movies = []
    if movie_ids:
        # Preserve order
        movies_dict = {m.id: m for m in Movie.query.filter(Movie.id.in_(movie_ids)).all()}
        movies = [movies_dict[mid] for mid in movie_ids if mid in movies_dict]
        
    return render_template('main/favorites.html', favorites=favorites, movies=movies)

@main_bp.route('/toggle-favorite/<int:movie_id>', methods=['POST'])
@login_required
def toggle_favorite(movie_id):
    favorite = Favorite.query.filter_by(user_id=current_user.id, movie_id=movie_id).first()
    
    if favorite:
        db.session.delete(favorite)
        db.session.commit()
        return jsonify({'status': 'removed'})
    else:
        new_favorite = Favorite(user_id=current_user.id, movie_id=movie_id)
        db.session.add(new_favorite)
        db.session.commit()
        return jsonify({'status': 'added'})


@main_bp.route('/movie/<int:movie_id>')
def movie_detail(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    
    # Increment views
    movie.views += 1
    db.session.commit()
    
    user_favorites = []
    if current_user.is_authenticated:
        user_favorites = [fav.movie_id for fav in Favorite.query.filter_by(user_id=current_user.id).all()]
    return render_template('main/detail.html', movie=movie, user_favorites=user_favorites, now=datetime.utcnow())

@main_bp.route('/watch/<int:episode_id>')
def watch(episode_id):
    episode = Episode.query.get_or_404(episode_id)
    movie = episode.movie
    
    # Check access permission
    can_watch = False
    if episode.is_free:
        can_watch = True
    elif current_user.is_authenticated:
        if current_user.subscription_end_date and current_user.subscription_end_date > datetime.utcnow():
            can_watch = True
        elif current_user.role == 'admin':
            can_watch = True
            
    if not can_watch:
        # If user not logged in, redirect to login (or show locked message)
        # If logged in but no sub, show upgrade message
        return render_template('main/watch_locked.html', movie=movie, episode=episode)

    return render_template('main/watch.html', movie=movie, episode=episode)

@main_bp.route('/subscribe')
@login_required
def subscribe():
    return redirect(url_for('main.profile', _anchor='pricing'))

@main_bp.route('/pricing')
def pricing():
    return redirect(url_for('main.profile', _anchor='pricing'))

@main_bp.route('/proxy')
def proxy():
    url = request.args.get('url')
    if not url:
        return "URL is required", 400
    
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
    
    # Forward Range header if present (important for video seeking)
    if 'Range' in request.headers:
        headers['Range'] = request.headers['Range']
    else:
        # Some servers require Range header for large media files
        headers['Range'] = 'bytes=0-'
    
    try:
        # Use stream=True to avoid loading large files into memory
        # verify=False is used because some CDNs might have certificate issues when accessed this way, 
        # though ideally it should be True. 
        req = requests.get(url, headers=headers, stream=True, verify=False)
        
        # Exclude some headers that shouldn't be forwarded or might cause issues
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        resp_headers = [(name, value) for (name, value) in req.headers.items()
                       if name.lower() not in excluded_headers]
        
        # Manually set Content-Length if available to allow progress bars
        if 'Content-Length' in req.headers:
            resp_headers.append(('Content-Length', req.headers['Content-Length']))
            
        # Add Accept-Ranges to support seeking
        resp_headers.append(('Accept-Ranges', 'bytes'))

        return Response(stream_with_context(req.iter_content(chunk_size=1024*16)), 
                       status=req.status_code, 
                       headers=resp_headers)
                       
    except requests.exceptions.RequestException as e:
        return f"Error fetching URL: {str(e)}", 500
