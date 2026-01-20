from flask import Blueprint, request, jsonify, current_app
from app.models import Transaction, db, User, SubscriptionPlan
from app.services.trakteer import TrakteerService
import json
from datetime import datetime, timedelta
from app import csrf

webhook_bp = Blueprint('webhook', __name__)

@webhook_bp.route('/trakteer', methods=['POST'])
@csrf.exempt
def trakteer_webhook():
    trakteer = TrakteerService()
    
    # Get raw data
    raw_data = request.get_data(as_text=True)
    current_app.logger.info(f"Webhook received. Headers: {dict(request.headers)}")
    current_app.logger.info(f"Webhook body: {raw_data}")
    
    # Verify Token
    token = request.headers.get('X-WEBHOOK-TOKEN')
    
    if not trakteer.verify_webhook(token):
        current_app.logger.warning("Webhook unauthorized or invalid signature")
        return jsonify({'status': 'unauthorized'}), 401
    
    try:
        data = json.loads(raw_data)
        message = data.get('supporter_message', '')
        current_app.logger.info(f"Supporter Message: {message}")
        transaction_id = trakteer.parse_webhook_message(message)
        current_app.logger.info(f"Parsed Transaction ID: {transaction_id}")
    except Exception as e:
        current_app.logger.error(f"Error parsing webhook data: {e}")
        return jsonify({'status': 'error'}), 400
    
    if not transaction_id:
        # Fallback: Check 'display_name' if 'support_message' doesn't contain Ref
        display_name = data.get('display_name', '')
        if display_name.startswith('Order #'):
             short_id = display_name.replace('Order #', '')
             current_app.logger.info(f"Trying to match Transaction via display_name: {short_id}")
             # Since transaction_id is int, we cast to string to search
             # But short_id is first 8 chars.
             # If IDs are small (1, 2, 3), short_id is just "1", "2", "3".
             # So we can try to cast short_id to int.
             try:
                 t_id = int(short_id)
                 transaction = Transaction.query.get(t_id)
                 if transaction:
                     transaction_id = str(transaction.id)
             except ValueError:
                 pass

    if not transaction_id:
        current_app.logger.info("Webhook ignored (no Transaction ID found)")
        return jsonify({'status': 'ignored'}), 200
    
    try:
        t_id_int = int(transaction_id)
    except ValueError:
        current_app.logger.error(f"Invalid Transaction ID format: {transaction_id}")
        return jsonify({'status': 'invalid_transaction_id'}), 400
        
    transaction = Transaction.query.get(t_id_int)
    if not transaction:
        current_app.logger.error(f"Transaction not found: {transaction_id}")
        return jsonify({'status': 'transaction_not_found'}), 404
        
    if transaction.status != 'paid':
        # Mark as paid
        transaction.status = 'paid'
        
        # Update User Subscription
        user = User.query.get(transaction.user_id)
        if user and transaction.plan_id:
            plan = SubscriptionPlan.query.get(transaction.plan_id)
            if plan:
                # Calculate new expiry
                now = datetime.utcnow()
                if user.subscription_end_date and user.subscription_end_date > now:
                    user.subscription_end_date += timedelta(days=plan.duration_days)
                else:
                    user.subscription_end_date = now + timedelta(days=plan.duration_days)
        
        db.session.commit()
        return jsonify({'status': 'success', 'transaction_id': transaction_id}), 200
    
    return jsonify({'status': 'already_paid'}), 200
