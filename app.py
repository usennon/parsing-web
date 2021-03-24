from flask import Flask, render_template, request, url_for, redirect, flash
from flask_bootstrap import Bootstrap
import requests
from bs4 import BeautifulSoup
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from forms import RegisterForm, LoginForm, CommentForm
from flask_ckeditor import CKEditor
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from flask_gravatar import Gravatar
from functools import wraps
from datetime import *
import os
from dotenv import load_dotenv


dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

app = Flask(__name__)
login_manager = LoginManager()
login_manager.init_app(app)
ckeditor = CKEditor(app)
Bootstrap(app)

Base = declarative_base()

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

app.config['SECRET_KEY'] = os.getenv(key='TOKEN')
##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///news.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


##CONFIGURE TABLES


class User(UserMixin, db.Model, Base):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, nullable=False, unique=True)
    password = db.Column(db.String, nullable=False, unique=True)
    name = db.Column(db.String, nullable=False, unique=True)
    comments = relationship('Comment', back_populates='author')


class News(db.Model, Base):
    __teblename__ = "news"
    id = db.Column(db.Integer, primary_key=True)
    article = db.Column(db.String, nullable=False, unique=True)
    body = db.Column(db.String, nullable=True)
    datet = db.Column(db.Date, nullable=False)
    img_url = db.Column(db.String, nullable=True)
    link = db.Column(db.String, nullable=False, unique=True)
    tag = db.Column(db.String, nullable=False)
    comments = relationship('Comment', back_populates='parent_post')


class Comment(db.Model, Base):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String, nullable=False)
    author = relationship('User', back_populates='comments')
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    parent_post_id = db.Column(db.Integer, ForeignKey('news.id'))
    parent_post = relationship('News', back_populates='comments')


db.create_all()


def make_soup(url):
    response = requests.get(url)
    data = response.text
    return BeautifulSoup(data, 'lxml')


def admin_only(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if current_user.id == 1:
            return func(*args, **kwargs)
        else:
            return 403

    return wrapper


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def home():
    soup1 = make_soup('https://www.rbc.ru')
    soup2 = make_soup('https://trends.rbc.ru/trends/short_news')

    trend_content = soup2.find_all('div', class_='item__inner')
    main_feed_links = soup1.find_all(name='a', class_='main__feed__link')

    main_news_dict = {}
    index = 0

    for content in trend_content:
        link = content.find(name='a').get('href')
        text = content.get_text().split('\n')
        text = [item for item in text if item != '']
        text_main = text[1].strip(' ')
        img = content.find(name='img').get('src')
        new_news = News(
            article=text_main,
            link=link,
            img_url=img,
            tag='main_trends',
            datet=date.today(),
        )
        db.session.add(new_news)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()

    trends = News.query.filter_by(tag='main_trends').all()

    for text in main_feed_links:
        main_news_dict[index] = [text.get('href'), text.get_text().strip('\n')]
        index += 1

    return render_template('index.html',
                           news=main_news_dict,
                           trends=trends,
                           current_user=current_user)


@app.route('/science-news')
def science():
    science_soup = make_soup('https://iz.ru/rubric/nauka')
    science_posts = science_soup.find_all(name='a', class_='node__cart__item__inside')

    for post in science_posts:
        link = 'https://iz.ru/' + post.get('href')
        text = post.get_text().strip().split('\n')[0]
        img = post.find(name='img').get('data-src')
        new_post = News(
            link=link,
            article=text,
            img_url=img,
            tag='science',
            datet=date.today()
        )
        db.session.add(new_post)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
    posts = News.query.filter_by(tag='science').all()
    return render_template('science.html', posts=posts)


@app.route('/society-news')
def society():
    soup = make_soup('https://www.rbc.ru/society/')
    society_posts = soup.find_all(name='a', class_='item__link')

    for post in society_posts:
        link = post.get('href')
        text = post.get_text().strip()
        img = post.find(name='img')
        try:
            image = img.get('src')
        except AttributeError:
            continue
        new_post = News(
            link=link,
            article=text,
            img_url=image,
            tag='society',
            datet=date.today()

        )
        db.session.add(new_post)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
    posts = News.query.filter_by(tag='society').all()
    return render_template('society.html', posts=posts)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('This email does not exist. Please try again')
            return redirect(url_for('login'))
        else:
            if check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for('home'))
            else:
                flash('Your password is incorrect. Please try again')
                return redirect(url_for('login'))
    return render_template('login.html', form=form)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        user = User.query.filter_by(email=email).first()
        if not user:
            hashed_pass = generate_password_hash(password)
            new_user = User(email=email,
                            password=hashed_pass,
                            name=name)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('home'))
        else:
            flash('Such user already exists. Log in!')
            return redirect(url_for('login'))
    return render_template('register.html', form=form, current_user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/show_news/<int:news_id>', methods=['GET', 'POST'])
def show_post(news_id):
    form = CommentForm()
    post = News.query.filter_by(id=news_id).first()
    soup = make_soup(post.link)
    if post.tag == 'science':
        content = soup.select_one('.text-article__inside p')
        body = content.get_text()
    else:
        try:
            body = soup.select_one('.article__text__overview span').string
        except AttributeError:
            body = soup.select_one('.article__text p').string

    post.body = body
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    if form.validate_on_submit() and request.method == 'POST':
        if current_user.is_authenticated:
            text = request.form.get('comment')
            new_comment = Comment(
                text=text,
                parent_post_id=news_id,
                author_id=current_user.id
            )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for('show_post', news_id=news_id))
        else:
            flash('You need to login or register to add a comment')
            return redirect(url_for('login'))

    return render_template('post.html',
                           post=post,
                           body=body,
                           form=form,
                           gravatar=gravatar,
                           current_user=current_user)


@app.route('/delete/<int:comment_id>')
def delete(comment_id):
    comment_to_delete = Comment.query.filter_by(id=comment_id).first()
    db.session.delete(comment_to_delete)
    db.session.commit()
    return redirect(url_for('show_post', news_id=comment_to_delete.parent_post_id))


# We don't want to keep an old news in our database.
# We can check database for old news every time client requests server
# But it may be a problem when we have a huge amount of news - checking the old
# news will be slow and burden the session.
# My suggestion is to give to the admin some control - he will decide when we
# need to clear our database from the old news.
@app.route('/clear-database')
@admin_only
def clear():
    day_now = date.today()
    news = News.query.all()
    for post in news:
        delta = day_now - post.datet
        if delta.days > 4:
            db.session.delete(post)
    db.session.commit()
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run()
