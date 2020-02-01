"""
                  ___
 walrus-mix    .-9 9 `\
             =(:(::)=  ;
               ||||     \
               ||||      `-.
              ,\|\|         `,
             /                \
            ;                  `'---.,
            |                         `\
            ;                     /     |
            \                    |      /
     jgs     )           \  __,.--\    /
          .-' \,..._\     \`   .-'  .-'
         `-=``      `:    |   /-/-/`
                      `.__/
"""
import datetime

from flask import Flask, redirect, render_template, request, g, abort, url_for, flash
from peewee import *
from wtforms.validators import Length
from wtfpeewee.fields import ModelHiddenField
from wtfpeewee.orm import model_form, ModelConverter


# config
DATABASE = 'example.db'
DEBUG = True
SECRET_KEY = 'my favorite food is walrus mix'

app = Flask(__name__)
app.config.from_object(__name__)

database = SqliteDatabase(DATABASE)

# request handlers
@app.before_request
def before_request():
    g.db = database
    g.db.connect()

@app.after_request
def after_request(response):
    g.db.close()
    return response

# model definitions
class BaseModel(Model):
    class Meta:
        database = database


class Post(BaseModel):
    title = CharField()
    content = TextField()
    pub_date = DateTimeField(default=datetime.datetime.now)

    def __unicode__(self):
        return self.title


class Comment(BaseModel):
    post = ForeignKeyField(Post, related_name='comments')
    name = CharField()
    comment = TextField()
    pub_date = DateTimeField(default=datetime.datetime.now)


# form classes
class HiddenForeignKeyConverter(ModelConverter):
    def handle_foreign_key(self, model, field, **kwargs):
        return field.name, ModelHiddenField(model=field.rel_model, **kwargs)


PostForm = model_form(Post, field_args={
    'title': dict(validators=[Length(min=3, max=200)]), # title must be at least 3 chars long
    'content': dict(description='this is the body of the post'), # a little help text
})
CommentForm = model_form(Comment, exclude=('pub_date',), converter=HiddenForeignKeyConverter())


def get_or_404(query, *expr):
    try:
        return query.where(*expr).get()
    except query.model.DoesNotExist:
        abort(404)

# views
@app.route('/')
def index():
    posts = (Post
             .select(Post, fn.COUNT(Comment.id).alias('comment_count'))
             .join(Comment, JOIN.LEFT_OUTER)
             .group_by(Post)
             .order_by(Post.pub_date.desc()))
    return render_template('posts/index.html', posts=posts)

@app.route('/<id>/')
def detail(id):
    post = get_or_404(Post.select(), Post.id == id)
    comment_form = CommentForm(post=post)
    return render_template('posts/detail.html', post=post, comment_form=comment_form)

@app.route('/add/', methods=['GET', 'POST'])
def add():
    post = Post()

    if request.method == 'POST':
        form = PostForm(request.form, obj=post)
        if form.validate():
            form.populate_obj(post)
            post.save()
            flash('Successfully added %s' % post, 'success')
            return redirect(url_for('detail', id=post.id))
    else:
        form = PostForm(obj=post)

    return render_template('posts/add.html', post=post, form=form)

@app.route('/<id>/edit/', methods=['GET', 'POST'])
def edit(id):
    post = get_or_404(Post.select(), Post.id == id)

    if request.method == 'POST':
        form = PostForm(request.form, obj=post)
        if form.validate():
            form.populate_obj(post)
            post.save()
            flash('Changes to %s saved successfully' % post.title, 'success')
            return redirect(url_for('detail', id=post.id))
    else:
        form = PostForm(obj=post)

    return render_template('posts/edit.html', post=post, form=form)

@app.route('/<id>/comment/', methods=['POST'])
def comment(id):
    post = get_or_404(Post.select(), Post.id == id)
    comment = Comment(post=post)
    form = CommentForm(request.form, obj=comment)
    if form.validate():
        form.populate_obj(comment)
        comment.save()
        flash('Thank you for your comment!', 'success')
    else:
        flash('There were errors with your comment', 'error')

    return redirect(url_for('detail', id=comment.post.id))



def create_tables():
    Post.create_table(True)
    Comment.create_table(True)

if __name__ == '__main__':
    create_tables()
    app.run()
