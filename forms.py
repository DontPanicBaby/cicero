# -*- coding:utf-8 -*-

from django.newforms import *
from django.conf import settings

from cicero.models import Topic, Article, Profile
from cicero.filters import filters

def model_field(model, fieldname, **kwargs):
    return model._meta.get_field(fieldname).formfield(**kwargs)

class PostForm(Form):
  text = model_field(Article, 'text', widget=Textarea(attrs={'cols': '80', 'rows': '20'}))
  name = CharField(label=u'Имя', required=False)
  
  def __init__(self, user, ip, *args, **kwargs):
    super(PostForm, self).__init__(*args, **kwargs)
    self.user, self.ip = user, ip

  def clean_name(self):
    if self.user.is_authenticated():
      return u''
    if not self.cleaned_data['name']:
      raise ValidationError('Обязательное поле')
    return self.cleaned_data['name']
  
  def _create_article(self, topic):
    user = self.user
    if not user.is_authenticated():
      from django.contrib.auth.models import User
      user = User.objects.get(username='cicero_guest')
    return topic.article_set.create(
      text=self.cleaned_data['text'], 
      author=user,
      ip=self.ip,
      guest_name=self.cleaned_data['name'],
      filter=user.cicero_profile.filter,
    )

class ArticleForm(PostForm):
  def __init__(self, topic, *args, **kwargs):
    super(ArticleForm, self).__init__(*args, **kwargs)
    self.topic = topic
    
  def save(self):
    return self._create_article(self.topic)
  
class TopicForm(PostForm):
  subject = model_field(Topic, 'subject')
  
  def __init__(self, forum, *args, **kwargs):
    super(TopicForm, self).__init__(*args, **kwargs)
    self.forum = forum
  
  def clean_subject(self):
    value = self.cleaned_data['subject'].strip()
    if not value:
      raise ValidationError(u'Тема не может состоять из одних пробелов')
    return value
  
  def save(self):
    topic = Topic(forum=self.forum, subject=self.cleaned_data['subject'])
    topic.save()
    return self._create_article(topic)

class ArticleEditForm(ModelForm):
  class Meta:
    model = Article
    fields = ['text', 'filter']
  
  def __init__(self, *args, **kwargs):
    super(ArticleEditForm, self).__init__(*args, **kwargs)
    self.fields['text'].widget = Textarea(attrs={'cols': '80', 'rows': '20'})

class AuthForm(Form):
  openid_url = CharField(label='OpenID', max_length=200, required=True)
  
  def __init__(self, session, *args, **kwargs):
    Form.__init__(self, *args, **kwargs)
    self.session = session
    
  def _site_url(self):
    from django.contrib.sites.models import Site
    site = Site.objects.get_current()
    return 'http://' + site.domain
  
  def clean_openid_url(self):
    from cicero.auth import create_request, OpenIdError
    try:
      self.request = create_request(self.cleaned_data['openid_url'], self.session)
    except OpenIdError, e:
      raise ValidationError(e)
    return self.cleaned_data['openid_url']
    
  def auth_redirect(self, target, view_name, acquire=None, args=[], kwargs={}):
    from django.core.urlresolvers import reverse
    site_url = self._site_url()
    trust_url = settings.OPENID_TRUST_URL or (site_url + '/')
    return_to = site_url + reverse(view_name, args=args, kwargs=kwargs)
    self.request.return_to_args['redirect'] = target
    if acquire:
      self.request.return_to_args['acquire_article'] = str(acquire.id)
    return self.request.redirectURL(trust_url, return_to)

class PersonalForm(ModelForm):
  class Meta:
    model = Profile
    fields = ['name']

class SettingsForm(ModelForm):
  class Meta:
    model = Profile
    fields = ['filter']

def TopicEditForm(instance, *args, **kwargs):
    def callback(field, **kwargs):
        if field.name == 'subject':
            formfield = field.formfield(**kwargs)
            formfield.label = u'Тема'
            return formfield
    return form_for_instance(instance, formfield_callback=callback)(*args, **kwargs)

class SpawnForm(Form):
  subject = model_field(Topic, 'subject')
  
  def __init__(self, article, *args, **kwargs):
    super(SpawnForm, self).__init__(*args, **kwargs)
    self.article = article
  
  def save(self):
    topic = Topic(forum=self.article.topic.forum, subject=self.cleaned_data['subject'])
    topic.save()
    topic.article_set.create(
      text=self.article.text,
      filter=self.article.filter,
      author=self.article.author,
      guest_name=self.article.guest_name
    )
    self.article.spawned_to = topic
    self.article.save()
    return topic