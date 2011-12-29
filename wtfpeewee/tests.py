import datetime
import unittest

from peewee import *
from wtforms import fields as wtfields
from wtforms.form import Form as WTForm
from wtfpeewee.fields import *
from wtfpeewee.orm import model_form


test_db = SqliteDatabase(':memory:')

class TestModel(Model):
    class Meta:
        database = test_db


class Blog(TestModel):
    title = CharField()
    
    def __unicode__(self):
        return self.title


class Entry(TestModel):
    pk = PrimaryKeyField()
    blog = ForeignKeyField(Blog)
    title = CharField(verbose_name='Wacky title')
    content = TextField()
    pub_date = DateTimeField(default=datetime.datetime.now)
    
    def __unicode__(self):
        return '%s: %s' % (self.blog.title, self.title)

BlogForm = model_form(Blog)
EntryForm = model_form(Entry)

class FakePost(dict):
    def getlist(self, key):
        val = self[key]
        if isinstance(val, list):
            return val
        return [val]


class WTFPeeweeTestCase(unittest.TestCase):
    def setUp(self):
        Entry.drop_table(True)
        Blog.drop_table(True)
        
        Blog.create_table()
        Entry.create_table()
        
        self.blog_a = Blog.create(title='a')
        self.blog_b = Blog.create(title='b')
        
        self.entry_a1 = Entry.create(blog=self.blog_a, title='a1', content='a1 content', pub_date=datetime.datetime(2011, 1, 1))
        self.entry_a2 = Entry.create(blog=self.blog_a, title='a2', content='a2 content', pub_date=datetime.datetime(2011, 1, 2))
        self.entry_b1 = Entry.create(blog=self.blog_b, title='b1', content='b1 content', pub_date=datetime.datetime(2011, 1, 1))
    
    def test_blog_form(self):
        form = BlogForm()
        self.assertEqual(form._fields.keys(), ['title'])
        self.assertTrue(isinstance(form.title, wtfields.TextField))
        self.assertEqual(form.data, {'title': None})
    
    def test_entry_form(self):
        form = EntryForm()
        self.assertEqual(sorted(form._fields.keys()), ['blog', 'content', 'pub_date', 'title'])
        
        self.assertTrue(isinstance(form.blog, ModelSelectField))
        self.assertTrue(isinstance(form.content, wtfields.TextAreaField))
        self.assertTrue(isinstance(form.pub_date, wtfields.DateTimeField))
        self.assertTrue(isinstance(form.title, wtfields.TextField))
        
        self.assertEqual(form.title.label.text, 'Wacky title')
        self.assertEqual(form.blog.label.text, 'Blog')
        self.assertEqual(form.pub_date.label.text, 'Pub Date')
        
        # check that the default value appears
        self.assertTrue(isinstance(form.pub_date.data, datetime.datetime))
        
        # check that the foreign key defaults to none
        self.assertEqual(form.blog.data, None)
        
        # check that the options look right
        self.assertEqual(list(form.blog.iter_choices()), [
            (self.blog_a.get_pk(), u'a', False), (self.blog_b.get_pk(), u'b', False)
        ])
    
    def test_blog_form_with_obj(self):
        form = BlogForm(obj=self.blog_a)
        self.assertEqual(form.data, {'title': 'a'})
        self.assertTrue(form.validate())
    
    def test_entry_form_with_obj(self):
        form = EntryForm(obj=self.entry_a1)
        self.assertEqual(form.data, {
            'title': 'a1',
            'content': 'a1 content',
            'pub_date': datetime.datetime(2011, 1, 1),
            'blog': self.blog_a,
        })
        self.assertTrue(form.validate())
        
        # check that the options look right
        self.assertEqual(list(form.blog.iter_choices()), [
            (self.blog_a.get_pk(), u'a', True), (self.blog_b.get_pk(), u'b', False)
        ])
    
    def test_blog_form_saving(self):
        form = BlogForm(FakePost({'title': 'new blog'}))
        self.assertTrue(form.validate())
        
        blog = Blog()
        form.populate_obj(blog)
        self.assertEqual(blog.title, 'new blog')

        # no new blogs were created
        self.assertEqual(Blog.select().count(), 2)
        
        # explicitly calling save will create the new blog
        blog.save()
        
        # make sure we created a new blog
        self.assertEqual(Blog.select().count(), 3)
        
        form = BlogForm(FakePost({'title': 'a edited'}), obj=self.blog_a)
        self.assertTrue(form.validate())
        form.populate_obj(self.blog_a)
        
        self.assertEqual(self.blog_a.title, 'a edited')
        self.blog_a.save()
        
        # make sure no new blogs were created
        self.assertEqual(Blog.select().count(), 3)
        
        # grab it from the database
        a = Blog.get(title='a edited')
    
    def test_entry_form_saving(self):
        # check count of entries
        self.assertEqual(Entry.select().count(), 3)
        
        form = EntryForm(FakePost({
            'title': 'new entry',
            'content': 'some content',
            'pub_date': '2011-02-01 00:00:00',
            'blog': self.blog_b.get_pk(),
        }))
        self.assertTrue(form.validate())
        
        self.assertEqual(form.pub_date.data, datetime.datetime(2011, 2, 1))
        self.assertEqual(form.blog.data, self.blog_b)
        
        entry = Entry()
        form.populate_obj(entry)
        
        # ensure entry count hasn't changed
        self.assertEqual(Entry.select().count(), 3)
        
        entry.save()
        self.assertEqual(Entry.select().count(), 4)
        self.assertEqual(self.blog_a.entry_set.count(), 2)
        self.assertEqual(self.blog_b.entry_set.count(), 2)
        
        # make sure the blog object came through ok
        self.assertEqual(entry.blog, self.blog_b)
        
        # edit entry a1
        form = EntryForm(FakePost({
            'title': 'a1 edited',
            'content': 'a1 content',
            'pub_date': '2011-01-01 00:00:00',
            'blog': self.blog_b.get_pk(),
        }), obj=self.entry_a1)
        self.assertTrue(form.validate())
        
        form.populate_obj(self.entry_a1)
        self.entry_a1.save()
        
        self.assertEqual(self.entry_a1.blog, self.blog_b)
        
        self.assertEqual(self.blog_a.entry_set.count(), 1)
        self.assertEqual(self.blog_b.entry_set.count(), 3)
        
        # pull from the db just to be 100% sure
        a1 = Entry.get(title='a1 edited')
        
        form = EntryForm(FakePost({
            'title': 'new',
            'content': 'blah',
            'pub_date': '2011-01-01 00:00:00',
            'blog': 10000
        }))
        self.assertFalse(form.validate())
    
    def test_form_with_only_exclude(self):
        frm = model_form(Entry, only=('title', 'content',))()
        self.assertEqual(sorted(frm._fields.keys()), ['content', 'title'])
        
        frm = model_form(Entry, exclude=('title', 'content',))()
        self.assertEqual(sorted(frm._fields.keys()), ['blog', 'pub_date'])
    
    def test_form_multiple(self):
        class TestForm(WTForm):
            blog = SelectMultipleQueryField(query=Blog.select())
        
        frm = TestForm()
        self.assertEqual([x for x in frm.blog.iter_choices()], [
            (self.blog_a.id, 'a', False),
            (self.blog_b.id, 'b', False),
        ])
        
        frm = TestForm(FakePost({'blog': [self.blog_b.id]}))
        self.assertEqual([x for x in frm.blog.iter_choices()], [
            (self.blog_a.id, 'a', False),
            (self.blog_b.id, 'b', True),
        ])
        self.assertEqual(frm.blog.data, [self.blog_b])
        self.assertTrue(frm.validate())
        
        frm = TestForm(FakePost({'blog': [self.blog_b.id, self.blog_a.id]}))
        self.assertEqual([x for x in frm.blog.iter_choices()], [
            (self.blog_a.id, 'a', True),
            (self.blog_b.id, 'b', True),
        ])
        self.assertEqual(frm.blog.data, [self.blog_a, self.blog_b])
        self.assertTrue(frm.validate())
        
        bad_id = [x for x in range(1,4) if x not in [self.blog_a.id, self.blog_b.id]][0]
        frm = TestForm(FakePost({'blog': [self.blog_b.id, bad_id]}))
        self.assertTrue(frm.validate())
    
    def test_hidden_field(self):
        class TestEntryForm(WTForm):
            blog = HiddenQueryField(query=Blog.select())
            title = wtfields.TextField()
            content = wtfields.TextAreaField()
        
        form = TestEntryForm(FakePost({
            'title': 'new entry',
            'content': 'some content',
            'blog': self.blog_b.get_pk(),
        }))
        
        # check the htmlz for the form's hidden field
        html = form._fields['blog']()
        self.assertEqual(html, u'<input id="blog" name="blog" type="hidden" value="%s">' % self.blog_b.get_pk())
        
        self.assertTrue(form.validate())
        self.assertEqual(form.blog.data, self.blog_b)
        
        entry = Entry()
        form.populate_obj(entry)
        
        # ensure entry count hasn't changed
        self.assertEqual(Entry.select().count(), 3)
        
        entry.save()
        self.assertEqual(Entry.select().count(), 4)
        self.assertEqual(self.blog_a.entry_set.count(), 2)
        self.assertEqual(self.blog_b.entry_set.count(), 2)
        
        # make sure the blog object came through ok
        self.assertEqual(entry.blog, self.blog_b)
        
        # edit entry a1
        form = TestEntryForm(FakePost({
            'title': 'a1 edited',
            'content': 'a1 content',
            'blog': self.blog_b.get_pk(),
        }), obj=self.entry_a1)
        
        # check the htmlz for the form's hidden field
        html = form._fields['blog']()
        self.assertEqual(html, u'<input id="blog" name="blog" type="hidden" value="%s">' % self.blog_b.get_pk())
        
        self.assertTrue(form.validate())
        
        form.populate_obj(self.entry_a1)
        self.entry_a1.save()
        
        self.assertEqual(self.entry_a1.blog, self.blog_b)
        
        self.assertEqual(self.blog_a.entry_set.count(), 1)
        self.assertEqual(self.blog_b.entry_set.count(), 3)
        
        # pull from the db just to be 100% sure
        a1 = Entry.get(title='a1 edited')
