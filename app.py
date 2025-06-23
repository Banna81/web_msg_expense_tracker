from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import re
from models import db, User, Expense, Category, SubCategory  # Assuming models.py contains the User model and db instance
from flask_migrate import Migrate  # Add this import
"""
render_template: Renders an HTML template file and returns it as a response to the client, often passing variables for dynamic content.
request: Represents the incoming HTTP request, allowing you to access form data, query parameters, headers, and more.
redirect: Returns a response that instructs the browser to navigate to a different URL.
url_for: Generates a URL for a given function name (route), making it easy to reference endpoints dynamically.
flash: Stores a message that can be retrieved and displayed to the user on the next request, commonly used for notifications.
"""
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'  
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)  # Add this line after db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
@login_manager.user_loader

def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/")
def home():
    return render_template('login.html')


@app.route('/register', methods = ['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        if User.query.filter_by(username = username).first():
            flash('Username already exists!', 'error')
        else:
            new_user = User(username = username, password = password )
            db.session.add(new_user)
            db.session.commit()

            flash('Registration Successful. Please login!', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods = ['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username = request.form['username']).first()

        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password!', 'error')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    category_totals = {}
    subcategory_breakdown = {}
    total_amount = 0

    for exp in expenses:
        cat_name = exp.category.name if exp.category else 'Other'
        subcat_name = exp.subcategory.name if exp.subcategory else 'Other'
        amount = exp.amount or 0
        # Category totals
        category_totals[cat_name] = category_totals.get(cat_name, 0) + amount
        # Subcategory breakdown
        if cat_name not in subcategory_breakdown:
            subcategory_breakdown[cat_name] = {}
        subcategory_breakdown[cat_name][subcat_name] = subcategory_breakdown[cat_name].get(subcat_name, 0) + amount
        total_amount += amount

    # Calculate percentages
    category_percentages = {}
    for cat, total in category_totals.items():
        category_percentages[cat] = (total / total_amount * 100) if total_amount > 0 else 0

    # Group categories <5% into 'Other'
    grouped_totals = {}
    grouped_percentages = {}
    grouped_subcats = {}
    other_total = 0
    other_subcats = {}
    for cat, percent in category_percentages.items():
        if percent < 5 and cat != 'Other':
            other_total += category_totals[cat]
            # Merge subcategories
            for subcat, sub_total in subcategory_breakdown[cat].items():
                other_subcats[subcat] = other_subcats.get(subcat, 0) + sub_total
        else:
            grouped_totals[cat] = category_totals[cat]
            grouped_percentages[cat] = percent
            grouped_subcats[cat] = subcategory_breakdown[cat]
    if other_total > 0:
        grouped_totals['Other'] = grouped_totals.get('Other', 0) + other_total
        grouped_percentages['Other'] = (other_total / total_amount * 100) if total_amount > 0 else 0
        # Merge with any existing 'Other' subcats
        if 'Other' in grouped_subcats:
            for subcat, sub_total in other_subcats.items():
                grouped_subcats['Other'][subcat] = grouped_subcats['Other'].get(subcat, 0) + sub_total
        else:
            grouped_subcats['Other'] = other_subcats

    # Calculate total spend of all categories (same as total_amount)
    total_spend = sum(grouped_totals.values())

    return render_template(
        'dashboard.html',
        username=current_user.username,
        expenses=expenses,
        categories=list(grouped_totals.keys()),
        totals=list(grouped_totals.values()),
        percentages=[grouped_percentages[cat] for cat in grouped_totals.keys()],
        subcategory_breakdown=grouped_subcats,
        total_spend=total_spend
    )


@app.route('/addmessage', methods=['GET','POST'])
@login_required
def add_expense():
    # Build a mapping from subcategory name to category name from the database
    subcategory_to_category = {}
    subcategories = SubCategory.query.all()
    for subcat in subcategories:
        subcategory_to_category[subcat.name.lower()] = subcat.category.name

    if request.method == 'POST':
        message = request.form['message']

        # --- Parse the message ---
        cleaned_message = message.replace(",", "")
        parsed_result = {
            'amount': 0.0,
            'merchant': '',
            'hashtags': [],
            'description': '',
            'category': 'Other',
            'subcategory': 'Other',
            'timestamp': datetime.now()
        }
        # extract amount
        amount_match = re.findall(r'\d+(?:\.\d+)?', cleaned_message)
        if amount_match:
            try:
                parsed_result['amount'] = float(amount_match[0])
            except ValueError:
                parsed_result['amount'] = 0.0
        # extract merchant
        merchant_match = re.findall(r'@\w+', cleaned_message)
        if merchant_match:
            parsed_result['merchant'] = merchant_match[0][1:]
        # extract hashtags (remove #)
        parsed_result['hashtags'] = [tag[1:] for tag in re.findall(r'#\w+', cleaned_message)]
        # extract description
        description = re.sub(r'@\w+', '', cleaned_message)
        description = re.sub(r'#\w+', '', description)
        description = re.sub(r'\d+(?:\.\d+)?', '', description)
        parsed_result['description'] = description.strip().lower()
        # match description keywords or hashtags to subcategory
        candidates = parsed_result['hashtags'] + parsed_result['description'].split()
        matched_subcat = None
        for word in candidates:
            word_lower = word.lower()
            if word_lower in subcategory_to_category:
                matched_subcat = word_lower
                break

        # Find category and subcategory objects from DB
        category_obj = Category.query.filter_by(name='Other').first()
        subcategory_obj = None
        if matched_subcat:
            subcategory_obj = SubCategory.query.filter_by(name=matched_subcat).first()
            if subcategory_obj:
                category_obj = subcategory_obj.category
                parsed_result['subcategory'] = subcategory_obj.name
                parsed_result['category'] = category_obj.name
        else:
            # fallback: try to match category by hashtag or description
            for word in candidates:
                cat = Category.query.filter_by(name=word.capitalize()).first()
                if cat:
                    category_obj = cat
                    parsed_result['category'] = cat.name
                    break

        # Save to DB
        new_expense = Expense(
            id=None,  # Auto-incremented by SQLAlchemy
            user_id=current_user.id,
            msg_unparsed=message,
            amount=parsed_result['amount'],
            merchant=parsed_result['merchant'],
            hashtags=parsed_result['hashtags'],
            description=parsed_result['description'],
            category_id=category_obj.id if category_obj else None,
            subcategory_id=subcategory_obj.id if subcategory_obj else None,
            timestamp=parsed_result['timestamp']
        )
        db.session.add(new_expense)
        db.session.commit()
        flash('Expense added!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_expenses.html')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_expense(id):
    expense = Expense.query.get_or_404(id)
    categories = Category.query.all()

    if expense.user_id != current_user.id:
        flash('Unauthorized access!', 'error')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        expense.title = request.form['title']
        expense.amount = float(request.form['amount'])
        expense.date = request.form['date']
        expense.category_id = request.form['category_id']

        db.session.commit()
        flash('Expense updated!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('edit_expenses.html', expense = expense, categories = categories)

@app.route('/delete/<int:id>')
@login_required
def delete_expense(id):
    expense = Expense.query.get_or_404(id)
    if expense.user_id != current_user.id:
        flash('Unauthorized access!', 'error')
        return redirect(url_for('dashboard'))

    db.session.delete(expense)
    db.session.commit()
    flash('Expense deleted!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# Categories CRUD
@app.route('/categories')
@login_required
def list_categories():
    categories = Category.query.all()
    return render_template('categories.html', categories=categories)


@app.route('/categories/add', methods=['GET', 'POST'])
@login_required
def add_category():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        subcat_names = request.form.getlist('subcat_names')
        subcat_descriptions = request.form.getlist('subcat_descriptions')

        if Category.query.filter_by(name=name).first():
            flash('Category already exists!', 'error')
        else:
            new_cat = Category(name=name, description=description)
            db.session.add(new_cat)
            db.session.flush()  # Get new_cat.id before commit

            # Add subcategories if provided
            for subcat_name, subcat_desc in zip(subcat_names, subcat_descriptions):
                if subcat_name.strip():
                    subcat = SubCategory(
                        name=subcat_name.strip(),
                        description=subcat_desc.strip(),
                        category_id=new_cat.id
                    )
                    db.session.add(subcat)
            db.session.commit()
            flash('Category and subcategories added!', 'success')
            return redirect(url_for('list_categories'))
    return render_template('add_category.html')

@app.route('/categories/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_category(id):
    category = Category.query.get_or_404(id)
    subcategories = SubCategory.query.filter_by(category_id=category.id).all()
    if request.method == 'POST':
        category.name = request.form['name']
        category.description = request.form['description']
        subcat_names = request.form.getlist('subcat_names')
        subcat_descriptions = request.form.getlist('subcat_descriptions')

        # Remove all existing subcategories for this category
        SubCategory.query.filter_by(category_id=category.id).delete()
        db.session.flush()

        # Add new/edited subcategories
        for subcat_name, subcat_desc in zip(subcat_names, subcat_descriptions):
            if subcat_name.strip():
                subcat = SubCategory(
                    name=subcat_name.strip(),
                    description=subcat_desc.strip(),
                    category_id=category.id
                )
                db.session.add(subcat)
        db.session.commit()
        flash('Category and subcategories updated!', 'success')
        return redirect(url_for('list_categories'))
    return render_template('add_category.html', category=category, subcategories=subcategories)

@app.route('/categories/delete/<int:id>')
@login_required
def delete_category(id):
    category = Category.query.get_or_404(id)
    db.session.delete(category)
    db.session.commit()
    flash('Category deleted!', 'success')
    return redirect(url_for('list_categories'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables if they don't exist
    app.run(debug=True)