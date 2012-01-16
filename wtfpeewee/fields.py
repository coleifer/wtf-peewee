"""
Useful form fields for use with the Peewee ORM.
(cribbed from wtforms.ext.django.fields)
"""
import operator
import warnings

from wtforms import widgets
from wtforms.fields import SelectFieldBase, HiddenField
from wtforms.validators import ValidationError


__all__ = (
    'ModelSelectField', 'ModelSelectMultipleField', 'ModelHiddenField',
    'SelectQueryField', 'SelectMultipleQueryField', 'HiddenQueryField'
)


class SelectQueryField(SelectFieldBase):
    """
    Given a SelectQuery either at initialization or inside a view, will display a
    select drop-down field of choices. The `data` property actually will
    store/keep an ORM model instance, not the ID. Submitting a choice which is
    not in the queryset will result in a validation error.

    Specify `get_label` to customize the label associated with each option. If
    a string, this is the name of an attribute on the model object to use as
    the label text. If a one-argument callable, this callable will be passed
    model instance and expected to return the label text. Otherwise, the model
    object's `__unicode__` will be used.

    If `allow_blank` is set to `True`, then a blank choice will be added to the
    top of the list. Selecting this choice will result in the `data` property
    being `None`.  The label for the blank choice can be set by specifying the
    `blank_text` parameter.
    """
    widget = widgets.Select()

    def __init__(self, label=None, validators=None, query=None, get_label=None, allow_blank=False, blank_text=u'', **kwargs):
        super(SelectQueryField, self).__init__(label, validators, **kwargs)
        self.allow_blank = allow_blank
        self.blank_text = blank_text or '----------------'
        self.query = query
        self.model = query.model
        self._set_data(None)
        
        if get_label is None:
            self.get_label = lambda o: unicode(o)
        elif isinstance(get_label, basestring):
            self.get_label = operator.attrgetter(get_label)
        else:
            self.get_label = get_label

    def get_model(self, pk):
        try:
            return self.query.get(**{
                self.model._meta.pk_name: pk
            })
        except self.query.model.DoesNotExist:
            pass

    def _get_data(self):
        if self._formdata is not None:
            self._set_data(self.get_model(self._formdata))
        return self._data

    def _set_data(self, data):
        self._data = data
        self._formdata = None

    data = property(_get_data, _set_data)
    
    def __call__(self, **kwargs):
        if 'value' in kwargs:
            self._set_data(self.get_model(kwargs['value']))
        return self.widget(self, **kwargs)

    def iter_choices(self):
        if self.allow_blank:
            yield (u'__None', self.blank_text, self.data is None)
        
        for obj in self.query.clone():
            yield (obj.get_pk(), self.get_label(obj), obj == self.data)

    def process_formdata(self, valuelist):
        if valuelist:
            if valuelist[0] == '__None':
                self.data = None
            else:
                self._data = None
                self._formdata = int(valuelist[0])

    def pre_validate(self, form):
        if self.data is not None:
            if not self.query.where(**{self.model._meta.pk_name: self.data.get_pk()}).exists():
                raise ValidationError(self.gettext('Not a valid choice'))
        elif not self.allow_blank:
            raise ValidationError(self.gettext('Selection cannot be blank'))


class SelectMultipleQueryField(SelectQueryField):
    widget = widgets.Select(multiple=True)
    
    def __init__(self, *args, **kwargs):
        kwargs.pop('allow_blank', None)
        super(SelectMultipleQueryField, self).__init__(*args, **kwargs)
    
    def get_model_list(self, pk_list):
        return list(self.query.where(**{
            '%s__in' % self.model._meta.pk_name: pk_list
        }))
    
    def _get_data(self):
        if self._formdata is not None:
            self._set_data(self.get_model_list(self._formdata))
        return self._data or []

    def _set_data(self, data):
        self._data = data
        self._formdata = None

    data = property(_get_data, _set_data)
    
    def __call__(self, **kwargs):
        if 'value' in kwargs:
            self._set_data(self.get_model_list(kwargs['value']))
        return self.widget(self, **kwargs)

    def iter_choices(self):
        for obj in self.query.clone():
            yield (obj.get_pk(), self.get_label(obj), obj in self.data)

    def process_formdata(self, valuelist):
        if valuelist:
            self._data = []
            self._formdata = map(int, valuelist)

    def pre_validate(self, form):
        if self.data:
            if not self.query.where(**{'%s__in' % self.model._meta.pk_name: [
                model.get_pk() for model in self.data
            ]}).count() == len(self.data):
                raise ValidationError(self.gettext('Not a valid choice'))


class HiddenQueryField(HiddenField):
    def __init__(self, label=None, validators=None, query=None, get_label=None, **kwargs):
        super(HiddenField, self).__init__(label, validators, **kwargs)
        self.query = query
        self.model = query.model
        self._set_data(None)

        if get_label is None:
            self.get_label = lambda o: unicode(o)
        elif isinstance(get_label, basestring):
            self.get_label = operator.attrgetter(get_label)
        else:
            self.get_label = get_label

    def get_model(self, pk):
        try:
            return self.query.get(**{
                self.model._meta.pk_name: pk
            })
        except self.query.model.DoesNotExist:
            pass

    def _get_data(self):
        if self._formdata is not None:
            self._set_data(self.get_model(self._formdata))
        return self._data

    def _set_data(self, data):
        self._data = data
        self._formdata = None

    data = property(_get_data, _set_data)
    
    def __call__(self, **kwargs):
        if 'value' in kwargs:
            self._set_data(self.get_model(kwargs['value']))
        return self.widget(self, **kwargs)
    
    def _value(self):
        return self.data and self.data.get_pk()

    def process_formdata(self, valuelist):
        if valuelist:
            self._data = None
            self._formdata = int(valuelist[0])


class ModelSelectField(SelectQueryField):
    """
    Like a SelectQueryField, except takes a model class instead of a
    queryset and lists everything in it.
    """
    def __init__(self, label=None, validators=None, model=None, **kwargs):
        super(ModelSelectField, self).__init__(label, validators, query=model.select(), **kwargs)


class ModelSelectMultipleField(SelectMultipleQueryField):
    """
    Like a SelectMultipleQueryField, except takes a model class instead of a
    queryset and lists everything in it.
    """
    def __init__(self, label=None, validators=None, model=None, **kwargs):
        super(ModelSelectMultipleField, self).__init__(label, validators, query=model.select(), **kwargs)

class ModelHiddenField(HiddenQueryField):
    """
    Like a HiddenQueryField, except takes a model class instead of a
    queryset and lists everything in it.
    """
    def __init__(self, label=None, validators=None, model=None, **kwargs):
        super(ModelHiddenField, self).__init__(label, validators, query=model.select(), **kwargs)
