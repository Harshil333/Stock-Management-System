from gc import disable
import os
import secrets
from PIL import Image
from functools import wraps
from datetime import datetime

from flask import render_template, url_for, flash, redirect, request, abort
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message

from stock_management import app, db, bcrypt, mail
from stock_management.forms import (RegistrationForm, LoginForm, UpdateAccountForm,
                             ProductForm, RequestResetForm, ResetPasswordForm ,BillingForm)
from stock_management.models import User, Product, Cart, Bill, Bill_Products


def requires_roles(*roles):
    def wrapper(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                # Redirect the user to an unauthorized notice!
                flash('You are not authorised to view this page.', 'danger')
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        return wrapped
    return wrapper


def produce_graph():
    if not current_user.is_authenticated:
        bills=Bill.query.filter().all()
        bills=list(filter(lambda x: float((x.date_created - datetime.now()).total_seconds())<604800,bills))
        newbill={"Mon":0,"Tue":0,"Wed":0,"Thu":0,"Fri":0,"Sat":0,"Sun":0}
        for x in bills:
            newbill[x.date_created.strftime("%a")]+=1
        return newbill
    else:
        if current_user.role=='Admin':
            bills=Bill.query.filter_by()
        else:
            bills=Bill.query.filter_by(author=current_user)
        bills=list(filter(lambda x: float((x.date_created - datetime.now()).total_seconds())<604800,bills))
        newbill={"Mon":0,"Tue":0,"Wed":0,"Thu":0,"Fri":0,"Sat":0,"Sun":0}
        for x in bills:
            newbill[x.date_created.strftime("%a")]+=1
        return newbill


############################ HOME ROUTES ##################################
@app.route("/")
@app.route("/home")
def home():
    newbill=produce_graph()
    return render_template('home.html',newbill=newbill)


############################ USER ROUTES ##################################
@app.route("/register", methods=['GET', 'POST'])
def register():
    newbill=produce_graph()
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        user.role = 'Customer'
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form,newbill=newbill)


@app.route("/login", methods=['GET', 'POST'])
def login():
    newbill=produce_graph()
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form,newbill=newbill)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn)

    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn


@app.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    newbill=produce_graph()
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your account has been updated!', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
    return render_template('account.html', title='Account', image_file=image_file, form=form,newbill=newbill)


def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request',
                  sender='youremailaddress@gmail.com',
                  recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link:
{url_for('reset_token', token=token, _external=True)}

If you did not make this request then simply ignore this email and no changes will be made.
'''
    mail.send(msg)


@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    newbill=produce_graph()
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_email(user)
        flash('An email has been sent with instructions to reset your password.', 'info')
        return redirect(url_for('login'))
    return render_template('reset_request.html', title='Reset Password', form=form,newbill=newbill)


@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    newbill=produce_graph()
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        flash('Your password has been updated! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('reset_token.html', title='Reset Password', form=form,newbill=newbill)


############################ PRODUCT ROUTES ##################################
@app.route("/product/new", methods=['GET', 'POST'])
@login_required
@requires_roles('Admin')
def new_product():
    newbill=produce_graph()
    form = ProductForm()
    if form.validate_on_submit():
        product = Product(name=form.name.data, discount=form.discount.data if form.discount.data else 0.00, quantity = form.quantity.data ,price = form.price.data, info = form.info.data, image_url= form.image_url.data, author=current_user)
        db.session.add(product)
        db.session.commit()
        flash('Your product has been added', 'success')
        return redirect(url_for('all_products'))
    form.discount.data=0.0
    return render_template('new_product.html', title='New Product', form=form, legend='New Product',newbill=newbill)


def search_product(product,q):
    if q in product.name or q in product.info:
        return True
    elif q.isnumeric() :
        if float(q)==product.id or float(q)==product.price:
            return True
    else:
        return False


@app.route("/allproducts")
@login_required
def all_products():
    page = request.args.get('page', 1, type=int)
    if request.args.get('search'):
        if current_user.role=='Admin':
            products = list(filter(lambda product : search_product(product,request.args.get('search')),Product.query.filter_by(author=current_user)))
        else:
            products = list(filter(lambda product : search_product(product,request.args.get('search')),Product.query.filter_by()))
        
        if len(products)==0:
            if current_user.role=='Admin':
                flash('Product not found. Please add the product first!','info')
                return redirect(url_for('new_product'))
            else:
                flash('Product not found. Please try again later!','info')
                return redirect(url_for('all_products'))
        
        return render_template('all_products.html', products = products, title="Searched Product", disabled=True)
    else:
        if current_user.role == 'Admin':
            p = list(Product.query.filter_by(author=current_user))
            products = Product.query.filter_by(author=current_user).order_by(Product.date_created.desc()).paginate(page = page, per_page = 4)
        else:
            p = Product.query.all()
            products = Product.query.filter_by().order_by(Product.date_created.desc()).paginate(page = page, per_page = 4)
        print(p)
        
        if len(p)==0:
            flash('No product present currently. Please try again later!','info')
            if current_user.role=='Admin':
                return redirect(url_for('new_product'))
            else:
                return redirect(url_for('home'))
    return render_template('all_products.html', products=products, title="All Products", disabled = False)


@app.route("/product/<int:product_id>")
@login_required
def product(product_id):
    newbill=produce_graph()
    product = Product.query.get_or_404(product_id)
    return render_template('product.html', title=product.name, product=product,newbill=newbill)


@app.route("/product/<int:product_id>/update", methods=['GET', 'POST'])
@login_required
@requires_roles('Admin')
def update_product(product_id):
    newbill=produce_graph()
    product = Product.query.get_or_404(product_id)
    if product.author != current_user:
        abort(403)
    form = ProductForm()
    if form.validate_on_submit():
        product.name = form.name.data
        product.price = form.price.data
        product.quantity = form.quantity.data
        product.discount = form.discount.data
        product.info = form.info.data
        product.image_url = form.image_url.data
        db.session.commit()
        flash('Your product has been updated!', 'success')
        return redirect(url_for('product', product_id=product.id))
    elif request.method == 'GET':
        form.name.data = product.name
        form.price.data = product.price
        form.quantity.data = product.quantity
        form.discount.data = product.discount 
        form.info.data = product.info
        form.image_url.data = product.image_url
    return render_template('new_product.html', title='Update product', form=form, legend='Update product',newbill=newbill)


@app.route("/product/<int:product_id>/delete", methods=['POST'])
@login_required
@requires_roles('Admin')
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    if product.author != current_user:
        abort(403)
    db.session.delete(product)
    db.session.commit()
    flash('Your product has been deleted!', 'success')
    return redirect(url_for('home'))


############################ CART ROUTES ##################################
@app.route("/cart")
@login_required
def cart():
    cart_items = Cart.query.filter_by(author=current_user)
    product_ids =[item.product_id for item in cart_items]
    products = [(Product.query.get(pid), product_ids.count(pid)) for pid in set(product_ids)]

    final_item_price, final_quantity, final_total  = 0, 0, 0
    for product in products:
        final_item_price += product[0].price*product[1]
        final_quantity += product[1]
        final_total += product[0].price*product[1]*(1-product[0].discount*0.01)
    final_discount = round((1-final_total/final_item_price)*100,2) if len(products)>0 else -100
    
    if final_discount==-100:
        flash('You have nothing in cart. Please add some products and then proceed','danger')
        return redirect(url_for('all_products'))
    return render_template('cart.html',title="Cart", products=products,final_item_price = final_item_price, final_quantity = final_quantity, final_total = final_total, final_discount=final_discount)


@app.route("/addtocart/<int:product_id>", methods=['GET','POST'])
@login_required
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    if product.author == current_user:
        abort(403)
    
    if product.quantity == 0:
        flash('Not enough units of this product. Try again later', 'warning')
        return redirect(url_for('cart'))
    
    product.quantity -= 1
    cart=Cart(author=current_user, product=product)
    db.session.add(cart)
    db.session.commit()
    flash('Product added to cart', 'success')
    next_page = request.args.get('next')
    return redirect(next_page) if next_page else redirect(url_for('cart'))


@app.route("/removefromcart/<int:product_id>", methods=['GET','POST'])
@login_required
def remove_from_cart(product_id):
    cart = Cart.query.filter_by(product_id=product_id)[0]
    if cart.author != current_user:
        abort(403)
    
    product = Product.query.get_or_404(product_id)
    product.quantity += 1
    db.session.delete(cart)
    db.session.commit()
    flash('Product removed from cart', 'success')
    return redirect(url_for('cart'))


@app.route("/cart/proceed",methods=["GET"])
@login_required
def proceed():
    form = BillingForm()
    cart_items = Cart.query.filter_by(author=current_user)
    product_ids =[item.product_id for item in cart_items]
    products = [(Product.query.get(pid), product_ids.count(pid)) for pid in set(product_ids)]

    final_item_price, final_quantity, final_total  = 0, 0, 0
    for product in products:
        final_item_price += product[0].price*product[1]
        final_quantity += product[1]
        final_total += product[0].price*product[1]*(1-product[0].discount*0.01)
    final_discount = round((1-final_total/final_item_price)*100,2) if len(products)>0 else -100
    
    if final_discount==-100:
        flash('You have nothing in cart. Please add some products and then proceed','danger')
        return redirect(url_for('all_products'))
    return render_template('proceed.html',form=form, products=products, final_item_price=final_item_price, final_quantity=final_quantity, final_total=final_total ,final_discount=final_discount, title="Summary", legend="Summary")


def send_stock_units_email(products_below_zero):
    try:
        msg = Message('Product Out of Stock',
                    sender='youremailaddress@gmail.com',
                    recipients=[i.author.email for i in products_below_zero])
        msg.body = f'''Dear admin,
    One of your products is out of stock. Please update the quantities for those products.
    
    If it is just a mistake from our side, then simply ignore this email and no changes will be made.

    Thanks and Regards,
    Team SMS
    '''
        mail.send(msg)
    except :
        flash('Unable to send mail. Try again later!','danger')


@app.route("/cart/confirmed", methods=["POST"])
@login_required
def confirmed():
    form=BillingForm()

    cart_items = Cart.query.filter_by(author=current_user)
    product_ids =[item.product_id for item in cart_items]
    products = [(Product.query.get(pid), product_ids.count(pid)) for pid in set(product_ids)]

    final_item_price, final_quantity, final_total  = 0, 0, 0
    for product in products:
        final_item_price += product[0].price*product[1]
        final_quantity += product[1]
        final_total += product[0].price*product[1]*(1-product[0].discount*0.01)
    final_discount = round((1-final_total/final_item_price)*100,2) if len(products)>0 else -100
    
    if form.validate_on_submit():
        total_bill = Bill(name = form.name.data, email = form.email.data, phonenumber = form.phone.data, total=final_item_price, final_price=final_total, discount=final_discount, author=current_user)
        db.session.add(total_bill)
        db.session.commit()

        for item in cart_items:
            bill_product = Bill_Products(bill=Bill.query.get(total_bill.id) , product=Product.query.get(item.product_id))
            db.session.add(bill_product)
            db.session.delete(item)
            db.session.commit()
        
        products_below_zero = []
        for product in products:
            if product[0].quantity == 0:
                products_below_zero.append(product[0])
        
        print("Products to be mailed: ", products_below_zero)
        send_stock_units_email(products_below_zero)

        flash('Bill created successfully', 'success')
        return redirect(url_for('home'))


############################ BILL ROUTES ##################################
def search_bill(bill,q):
    if q in bill.name:
        return True
    elif q.isnumeric():
        if float(q)==bill.id or float(q)==bill.final_price:
            return True
    else:
        return False

    
@app.route("/bills",methods=["GET", "POST"])
@login_required
def all_bills():
    newbill=produce_graph()
    page = request.args.get('page', 1, type=int)
    if request.args.get('search'):
        if current_user.role=='Customer':
            bills = list(filter(lambda bill : search_bill(bill, request.args.get('search')), Bill.query.filter_by(author=current_user)))
        else:
            bills = list(filter(lambda bill : search_bill(bill, request.args.get('search')), Bill.query.filter_by()))

        if len(bills)==0:
            flash('Bill not found.','info')
            return redirect(url_for('all_bills'))
        return render_template('view_all_bills.html', bills=bills, title="Searched Bill", disabled=True, newbill=newbill)

    else:
        if current_user.role == 'Customer':
            b = list(Bill.query.filter_by(author=current_user))
            bills = Bill.query.filter_by(author=current_user).order_by(Bill.date_created.desc()).paginate(page = page, per_page = 2)
        else:
            b = Bill.query.all()
            bills = Bill.query.filter_by().order_by(Bill.date_created.desc()).paginate(page = page, per_page = 2)
        print(b)
        if len(b)==0:
            flash('No bills present currently. Please try again later!','info')
            if current_user.role=='Customer':
                return redirect(url_for('all_products'))
            else:
                return redirect(url_for('home'))

    return render_template('view_all_bills.html', title="Bills", bills = bills, newbill = newbill, disabled = False)    


@app.route("/bill/<int:bill_id>",methods=["GET","POST"])
@login_required
def particular_bill(bill_id):
    newbill=produce_graph()
    bill = Bill.query.get_or_404(bill_id)
    print("Bill:",bill)
    products = list(Bill_Products.query.filter_by(bill_id=bill.id))
    print("Products in this Bill:", products)
    products = [ Product.query.get(x.product_id) for x in products ]
    products = [ (x,products.count(x)) for x in set(products) ]
    print("Final Products:", products)

    final_quantity=0
    final_total=0
    final_discount=0
    final_item_price=0
    for product in products:
        final_item_price+=product[0].price*product[1]
        final_quantity+=product[1]
        final_total+=product[1]*product[0].price*(1-product[0].discount*0.01)
    final_discount = round((1-final_total/final_item_price)*100,2) if len(products)>0 else -100

    return render_template('view_particular_bill.html', title="Bill", final_quantity=final_quantity, final_total=final_total, final_item_price=final_item_price, bill=bill, final_discount=final_discount, products=products, newbill=newbill)