"""
Tools for generating forms based on Peewee models
(cribbed from wtforms.ext.django)
"""
from collections import namedtuple
from decimal import Decimal
from wtforms import Form
from wtforms import fields as f
from wtforms import ValidationError
from wtforms import validators
from wtfpeewee.fields import ModelSelectField
from wtfpeewee.fields import SelectChoicesField
from wtfpeewee.fields import WPDateField
from wtfpeewee.fields import WPDateTimeField
from wtfpeewee.fields import WPTimeField
from wtfpeewee._compat import text_type

from peewee import BigIntegerField
from peewee import BlobField
from peewee import BooleanField
from peewee import CharField
from peewee import DateField
from peewee import DateTimeField
from peewee import DecimalField
from peewee import DoesNotExist
from peewee import DoubleField
from peewee import FloatField
from peewee import ForeignKeyField
from peewee import IntegerField
from peewee import PrimaryKeyField
from peewee import TextField
from peewee import TimeField


__all__ = (
    'FieldInfo',
    'ModelConverter',
    'model_fields',
    'model_form')

def handle_null_filter(data):
    if data == '':
        return None
    return data

FieldInfo = namedtuple('FieldInfo', ('name', 'field'))

class ModelConverter(object):
    defaults = {
        BigIntegerField: f.IntegerField,
        BlobField: f.TextAreaField,
        BooleanField: f.BooleanField,
        CharField: f.TextField,
        DateField: WPDateField,
        DateTimeField: WPDateTimeField,
        DecimalField: f.DecimalField,
        DoubleField: f.FloatField,
        FloatField: f.FloatField,
        IntegerField: f.IntegerField,
        PrimaryKeyField: f.HiddenField,
        TextField: f.TextAreaField,
        TimeField: WPTimeField,
    }
    coerce_defaults = {
        BigIntegerField: int,
        CharField: text_type,
        DoubleField: float,
        FloatField: float,
        IntegerField: int,
        TextField: text_type,
    }
    required = (
        CharField,
        DateTimeField,
        ForeignKeyField,
        PrimaryKeyField,
        TextField)

    def __init__(self, additional=None, additional_coerce=None):
        self.converters = {ForeignKeyField: self.handle_foreign_key}
        if additional:
            self.converters.update(additional)

        self.coerce_settings = dict(self.coerce_defaults)
        if additional_coerce:
            self.coerce_settings.update(additional_coerce)

    def handle_foreign_key(self, model, field, **kwargs):
        if field.null:
            kwargs['allow_blank'] = True
        if field.choices is not None:
            field_obj = SelectQueryField(query=field.choices, **kwargs)
        else:
            field_obj = ModelSelectField(model=field.rel_model, **kwargs)
        return FieldInfo(field.name, field_obj)

    def convert(self, model, field, field_args):
        kwargs = {
            'label': field.verbose_name,
            'validators': [],
            'filters': [],
            'default': field.default,
            'description': field.help_text}
        if field_args:
            kwargs.update(field_args)

        if field.null:
            # Treat empty string as None when converting.
            kwargs['filters'].append(handle_null_filter)

        if (field.null or (field.default is not None)) and not field.choices:
            # If the field can be empty, or has a default value, do not require
            # it when submitting a form.
            kwargs['validators'].append(validators.Optional())
        else:
            if isinstance(field, self.required):
                kwargs['validators'].append(validators.Required())

        field_class = type(field)
        if field_class in self.converters:
            return self.converters[field_class](model, field, **kwargs)
        elif field_class in self.defaults:
            if issubclass(self.defaults[field_class], f.FormField):
                # FormField fields (i.e. for nested forms) do not support
                # filters.
                kwargs.pop('filters')
            if field.choices or 'choices' in kwargs:
                choices = kwargs.pop('choices', field.choices)
                if field_class in self.coerce_settings or 'coerce' in kwargs:
                    coerce_fn = kwargs.pop('coerce',
                                           self.coerce_settings[field_class])
                    allow_blank = kwargs.pop('allow_blank', field.null)
                    kwargs.update({
                        'choices': choices,
                        'coerce': coerce_fn,
                        'allow_blank': allow_blank})

                    return FieldInfo(field.name, SelectChoicesField(**kwargs))

            return FieldInfo(field.name, self.defaults[field_class](**kwargs))

        raise AttributeError("There is not possible conversion "
                             "for '%s'" % field_class)


def model_fields(model, allow_pk=False, only=None, exclude=None,
                 field_args=None, converter=None):
    """
    Generate a dictionary of fields for a given Peewee model.

    See `model_form` docstring for description of parameters.
    """
    converter = converter or ModelConverter()
    field_args = field_args or {}

    model_fields = list(model._meta.get_sorted_fields())
    if not allow_pk:
        model_fields.pop(0)

    if only:
        model_fields = [x for x in model_fields if x[0] in only]
    elif exclude:
        model_fields = [x for x in model_fields if x[0] not in exclude]

    field_dict = {}
    for name, model_field in model_fields:
        name, field = converter.convert(model, model_field, field_args.get(name))
        field_dict[name] = field

    return field_dict


def model_form(model, base_class=Form, allow_pk=False, only=None, exclude=None,
               field_args=None, converter=None):
    """
    Create a wtforms Form for a given Peewee model class::

        from wtfpeewee.orm import model_form
        from myproject.myapp.models import User
        UserForm = model_form(User)

    :param model:
        A Peewee model class
    :param base_class:
        Base form class to extend from. Must be a ``wtforms.Form`` subclass.
    :param only:
        An optional iterable with the property names that should be included in
        the form. Only these properties will have fields.
    :param exclude:
        An optional iterable with the property names that should be excluded
        from the form. All other properties will have fields.
    :param field_args:
        An optional dictionary of field names mapping to keyword arguments used
        to construct each field object.
    :param converter:
        A converter to generate the fields based on the model properties. If
        not set, ``ModelConverter`` is used.
    """
    field_dict = model_fields(model, allow_pk, only, exclude, field_args, converter)
    return type(model.__name__ + 'Form', (base_class, ), field_dict)
