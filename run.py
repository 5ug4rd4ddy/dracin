from app import create_app, db
from app.models import User, Movie, Episode, SubscriptionPlan

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Movie': Movie, 'Episode': Episode, 'SubscriptionPlan': SubscriptionPlan}

if __name__ == '__main__':
    app.run(debug=True, port=5000)
