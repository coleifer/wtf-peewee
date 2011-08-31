# wtf-peewee

this project, based on the code found in ``wtforms.ext``, provides a bridge
between peewee models and wtforms, mapping model fields to form fields.

## example usage:

    from peewee import *
    from wtfpeewee.orm import model_form

    class Blog(Model):
        name = CharField()
        
        def __unicode__(self):
            return self.name

    class Entry(Model):
        blog = ForeignKeyField(Blog)
        title = CharField()
        body = TextField()

        def __unicode__(self):
            return self.title

    # create a form class for use with the Entry model
    EntryForm = model_form(Entry)
