from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.models import db, Transaction, SubscriptionPlan
import os
from werkzeug.utils import secure_filename
from app.services.trakteer import TrakteerService

payment_bp = Blueprint('payment', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@payment_bp.route('/checkout/<int:plan_id>', methods=['GET', 'POST'])
@login_required
def checkout(plan_id):
    plan = SubscriptionPlan.query.get_or_404(plan_id)
    if request.method == 'POST':
        # Trakteer QRIS
        if request.form.get('payment_method') == 'qris':
             transaction = Transaction(
                 user_id=current_user.id,
                 plan_id=plan.id,
                 amount=plan.price,
                 status='pending'
             )
             db.session.add(transaction)
             db.session.commit()
             
             try:
                 trakteer = TrakteerService()
                 qris_content = trakteer.get_qris(transaction.id, int(plan.price), current_user.email)
                 
                 transaction.qris_content = qris_content
                 db.session.commit()
                 
                 return redirect(url_for('payment.pay', transaction_id=transaction.id))
             except Exception as e:
                 db.session.delete(transaction)
                 db.session.commit()
                 flash(f"Error generating QRIS: {e}", 'error')
                 return redirect(request.url)

        # Manual Upload
        if 'payment_proof' in request.files:
            file = request.files['payment_proof']
            if file.filename == '':
                flash('No selected file')
                return redirect(request.url)
            if file and allowed_file(file.filename):
                filename = secure_filename(f"proof_{int(os.times().system)}_{file.filename}")
                # Ensure upload folder exists
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'proofs')
                os.makedirs(upload_folder, exist_ok=True)
                
                file.save(os.path.join(upload_folder, filename))
                
                transaction = Transaction(
                    user_id=current_user.id,
                    plan_id=plan.id,
                    amount=plan.price,
                    payment_proof=filename,
                    status='pending'
                )
                db.session.add(transaction)
                db.session.commit()
                flash('Payment proof uploaded successfully! Please wait for admin approval.', 'success')
                return redirect(url_for('main.profile'))
            
    return render_template('payment/checkout.html', plan=plan)

@payment_bp.route('/pay/<int:transaction_id>')
@login_required
def pay(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    if transaction.user_id != current_user.id:
        flash("Unauthorized access", "error")
        return redirect(url_for('main.index'))
        
    return render_template('payment/pay.html', transaction=transaction)

@payment_bp.route('/check_status/<int:transaction_id>')
@login_required
def check_status(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    if transaction.user_id != current_user.id:
        return {'status': 'unauthorized'}, 401
    return {'status': transaction.status}
