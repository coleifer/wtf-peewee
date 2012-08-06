"""
Tools for generating forms based on Peewee models
(cribbed from wtforms.ext.django)
"""
from decimal import Decimal
from wtforms import fields as f
from wtforms import Form
from wtforms import validators, ValidationError
from wtfpeewee.fields import ModelSelectField, SelectChoicesField

from peewee import PrimaryKeyField, IntegerField, FloatField, DateTimeField,\
    BooleanField, CharField, TextField, ForeignKeyField, DecimalField, DateField,\
    TimeField, DoesNotExist, IntegerColumn, FloatColumn, DoubleColumn


__all__ = (
    'model_fields', 'model_form',
)

def handle_null_filter(data):
    if data == '':
        return None
    return data


class Unique(object):
    """Checks field value unicity against specified table field.

    :param model:
        The model to check unicity against.
    :param column:
        The unique column.
    :param message:
        The error message.
    """

    def __init__(self, model, column, message=None):
        self.model = model
        self.column = column
        self.message = message

    def __call__(self, form, field):
        try:
            obj = self.model.get(**{self.column:field.data})
            if obj and obj.get_field_dict() != form.data:  # dupicate
                if self.message is None:
                    self.message = field.gettext('Already exists.')
                raise ValidationError(self.message)
        except DoesNotExist:
            pass


class ModelConverter(object):
    defaults = {
        PrimaryKeyField: f.HiddenField,
        IntegerField: f.IntegerField,
        FloatField: f.FloatField,
        DecimalField: f.DecimalField,
        DateTimeField: f.DateTimeField,
        DateField: f.DateField,
        TimeField: f.TextField,
        BooleanField: f.BooleanField,
        CharField: f.TextField,
        TextField: f.TextAreaField,
    }
    coerce_defaults = {
        IntegerField: int,
        FloatField: float,
        CharField: unicode,
        TextField: unicode,
    }
    required = (DateTimeField, CharField, TextField, ForeignKeyField, PrimaryKeyField)
    
    def __init__(self, additional=None, additional_coerce=None):
        self.converters = {
            ForeignKeyField: self.handle_foreign_key,
        }
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
            field_obj = ModelSelectField(model=field.to, **kwargs)
        return field.name, field_obj
    
    def handle_primary_key(self, model, field, **kwargs):
        if field.column_class == IntegerColumn:
            field_obj = f.IntegerField(**kwargs)
        elif field.column_class in (FloatColumn, DoubleColumn):
            field_obj = f.FloatField(**kwargs)
        else:
            field_obj = f.TextField(**kwargs)
        return field.name, field_obj

    def add_primary_key_handler(self):
        self.converters.update({PrimaryKeyField: self.handle_primary_key})

    def convert(self, model, field, field_args):
        kwargs = dict(
            label=field.verbose_name,
            validators=[],
            filters=[],
            default=field.default,
            description=field.help_text,
        )
        if field_args:
            kwargs.update(field_args)
        
        if field.null:
            kwargs['filters'].append(handle_null_filter)
        elif field.default is not None:
            kwargs['validators'].append(validators.Optional())
        else:
            if isinstance(field, self.required):
                kwargs['validators'].append(validators.Required())
        
        if isinstance(field, PrimaryKeyField):
            kwargs['validators'].append(Unique(model, field.name))
        elif field.unique:
            kwargs['validators'].append(Unique(model, field.name))

        field_class = type(field)
        
        if field_class in self.converters:
            return self.converters[field_class](model, field, **kwargs)
        elif field_class in self.defaults:
            if field.choices or 'choices' in kwargs:
                choices = kwargs.pop('choices', field.choices)
                if field_class in self.coerce_settings or 'coerce' in kwargs:
                    coerce_fn = kwargs.pop('coerce', self.coerce_settings[field_class])
                    allow_blank = kwargs.pop('allow_blank', field.null)
                    kwargs.update(dict(choices=choices, coerce=coerce_fn, allow_blank=allow_blank))
                    return field.name, SelectChoicesField(**kwargs)
            
            return field.name, self.defaults[field_class](**kwargs)


def model_fields(model, allow_pk=False, only=None, exclude=None, field_args=None, converter=None):
    """
    Generate a dictionary of fields for a given Peewee model.

    See `model_form` docstring for description of parameters.
    """
    converter = converter or ModelConverter()
    field_args = field_args or {}

    model_fields = list(model._meta.get_sorted_fields())

    if not allow_pk:
        model_fields.pop(0)
    else:
        converter.add_primary_key_handler()

    if only:
        model_fields = (x for x in model_fields if x[0] in only)
    elif exclude:
        model_fields = (x for x in model_fields if x[0] not in exclude)

    field_dict = {}
    for name, model_field in model_fields:
        field_info = converter.convert(model, model_field, field_args.get(name))
        if field_info is not None:
            field_name, field_obj = field_info
            field_dict[field_name] = field_obj

    return field_dict


def model_form(model, base_class=Form, allow_pk=False, only=None, exclude=None, field_args=None, converter=None):
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
