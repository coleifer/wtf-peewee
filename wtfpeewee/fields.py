"""
Useful form fields for use with the Peewee ORM.
(cribbed from wtforms.ext.django.fields)
"""
import datetime
import operator
import warnings

from wtforms import fields, form, widgets
from wtforms.fields import FormField, _unset_value
from wtforms.validators import ValidationError
from wtforms.widgets import HTMLString, html_params


__all__ = (
    'ModelSelectField', 'ModelSelectMultipleField', 'ModelHiddenField',
    'SelectQueryField', 'SelectMultipleQueryField', 'HiddenQueryField',
    'SelectChoicesField', 'BooleanSelectField', 'WPTimeField', 'WPDateField',
    'WPDateTimeField',
)


class StaticAttributesMixin(object):
    attributes = {}

    def __call__(self, **kwargs):
        for key, value in self.attributes.items():
            if key in kwargs:
                curr = kwargs[key]
                kwargs[key] = '%s %s' % (value, curr)
        return super(StaticAttributesMixin, self).__call__(**kwargs)


class BooleanSelectField(fields.SelectFieldBase):
    widget = widgets.Select()

    def iter_choices(self):
        yield ('1', 'True', self.data)
        yield ('', 'False', not self.data)

    def process_data(self, value):
        try:
            self.data = bool(value)
        except (ValueError, TypeError):
            self.data = None

    def process_formdata(self, valuelist):
        if valuelist:
            try:
                self.data = bool(valuelist[0])
            except ValueError:
                raise ValueError(self.gettext(u'Invalid Choice: could not coerce'))


class WPTimeField(StaticAttributesMixin, fields.TextField):
    attributes = {'class': 'time-widget'}

    def __init__(self, label=None, validators=None, format='%H:%M:%S', **kwargs):
        super(WPTimeField, self).__init__(label, validators, **kwargs)
        self.format = format

    def _value(self):
        if self.raw_data:
            return u' '.join(self.raw_data)
        else:
            return self.data and self.data.strftime(self.format) or u''

    def process_formdata(self, valuelist):
        if valuelist:
            date_str = u' '.join(valuelist)
            try:
                self.data = datetime.datetime.strptime(date_str, self.format).time()
            except ValueError:
                try:
                    self.data = datetime.datetime.strptime(date_str, '%H:%M').time()
                except ValueError:
                    self.data = None
                    raise ValueError(self.gettext(u'Not a valid time value'))


class WPDateField(StaticAttributesMixin, fields.DateField):
    attributes = {'class': 'date-widget'}


def datetime_widget(field, **kwargs):
    kwargs.setdefault('id', field.id)
    kwargs.setdefault('class', '')
    kwargs['class'] += ' datetime-widget'
    html = []
    for subfield in field:
        html.append(subfield(**kwargs))
    return HTMLString(u''.join(html))


class _DateTimeForm(form.Form):
    date = WPDateField()
    time = WPTimeField()


class WPDateTimeField(FormField):
    widget = staticmethod(datetime_widget)

    def __init__(self, label='', validators=None, **kwargs):
        validators = None
        super(WPDateTimeField, self).__init__(
            _DateTimeForm, label, validators,
            **kwargs
        )

    def process(self, formdata, data=_unset_value):
        prefix = self.name + self.separator
        kwargs = {}
        if data is _unset_value:
            try:
                data = self.default()
            except TypeError:
                data = self.default

        if data and data is not _unset_value:
            kwargs['date'] = data.date()
            kwargs['time'] = data.time()

        self.form = self.form_class(formdata, prefix=prefix, **kwargs)

    def populate_obj(self, obj, name):
        setattr(obj, name, self.data)

    @property
    def data(self):
        if self.date.data is not None and self.time.data is not None:
            return datetime.datetime.combine(self.date.data, self.time.data)


class ChosenSelectWidget(widgets.Select):
    """
        `Chosen <http://harvesthq.github.com/chosen/>`_ styled select widget.

        You must include chosen.js for styling to work.
    """
    def __call__(self, field, **kwargs):
        if field.allow_blank and not self.multiple:
            kwargs['data-role'] = u'chosenblank'
        else:
            kwargs['data-role'] = u'chosen'

        return super(ChosenSelectWidget, self).__call__(field, **kwargs)


class SelectChoicesField(fields.SelectField):
    widget = ChosenSelectWidget()

    # all of this exists so i can get proper handling of None
    def __init__(self, label=None, validators=None, coerce=unicode, choices=None, allow_blank=False, blank_text=u'', **kwargs):
        super(SelectChoicesField, self).__init__(label, validators, coerce, choices, **kwargs)
        self.allow_blank = allow_blank
        self.blank_text = blank_text or '----------------'

    def iter_choices(self):
        if self.allow_blank:
            yield (u'__None', self.blank_text, self.data is None)

        for value, label in self.choices:
            yield (value, label, self.coerce(value) == self.data)

    def process_data(self, value):
        if value is None:
            self.data = None
        else:
            try:
                self.data = self.coerce(value)
            except (ValueError, TypeError):
                self.data = None

    def process_formdata(self, valuelist):
        if valuelist:
            if valuelist[0] == '__None':
                self.data = None
            else:
                try:
                    self.data = self.coerce(valuelist[0])
                except ValueError:
                    raise ValueError(self.gettext(u'Invalid Choice: could not coerce'))

    def pre_validate(self, form):
        if self.allow_blank and self.data is None:
            return
        super(SelectChoicesField, self).pre_validate(form)


class SelectQueryField(fields.SelectFieldBase):
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
    widget = ChosenSelectWidget()

    def __init__(self, label=None, validators=None, query=None, get_label=None, allow_blank=False, blank_text=u'', **kwargs):
        super(SelectQueryField, self).__init__(label, validators, **kwargs)
        self.allow_blank = allow_blank
        self.blank_text = blank_text or '----------------'
        self.query = query
        self.model = query.model_class
        self._set_data(None)

        if get_label is None:
            self.get_label = lambda o: unicode(o)
        elif isinstance(get_label, basestring):
            self.get_label = operator.attrgetter(get_label)
        else:
            self.get_label = get_label

    def get_model(self, pk):
        try:
            return self.query.where(self.model._meta.primary_key==pk).get()
        except self.model.DoesNotExist:
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
            yield (obj.get_id(), self.get_label(obj), obj == self.data)

    def process_formdata(self, valuelist):
        if valuelist:
            if valuelist[0] == '__None':
                self.data = None
            else:
                self._data = None
                self._formdata = valuelist[0]

    def pre_validate(self, form):
        if self.data is not None:
            if not self.query.where(self.model._meta.primary_key==self.data.get_id()).exists():
                raise ValidationError(self.gettext('Not a valid choice'))
        elif not self.allow_blank:
            raise ValidationError(self.gettext('Selection cannot be blank'))


class SelectMultipleQueryField(SelectQueryField):
    widget =  ChosenSelectWidget(multiple=True)

    def __init__(self, *args, **kwargs):
        kwargs.pop('allow_blank', None)
        super(SelectMultipleQueryField, self).__init__(*args, **kwargs)

    def get_model_list(self, pk_list):
        return list(self.query.where(self.model._meta.primary_key << pk_list))

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
            yield (obj.get_id(), self.get_label(obj), obj in self.data)

    def process_formdata(self, valuelist):
        if valuelist:
            self._data = []
            self._formdata = map(int, valuelist)

    def pre_validate(self, form):
        if self.data:
            id_list = [m.get_id() for m in self.data]
            if not self.query.where(self.model._meta.primary_key << id_list).count() == len(id_list):
                raise ValidationError(self.gettext('Not a valid choice'))


class HiddenQueryField(fields.HiddenField):
    def __init__(self, label=None, validators=None, query=None, get_label=None, **kwargs):
        super(fields.HiddenField, self).__init__(label, validators, **kwargs)
        self.query = query
        self.model = query.model_class
        self._set_data(None)

        if get_label is None:
            self.get_label = lambda o: unicode(o)
        elif isinstance(get_label, basestring):
            self.get_label = operator.attrgetter(get_label)
        else:
            self.get_label = get_label

    def get_model(self, pk):
        try:
            return self.query.where(self.model._meta.primary_key==pk).get()
        except self.model.DoesNotExist:
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
        return self.data and self.data.get_id()

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
