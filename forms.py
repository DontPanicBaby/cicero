# -*- coding:utf-8 -*-

from django.newforms import *
from django.conf import settings

def _create_article(topic, user, data):
  if not user.is_authenticated():
    from django.contrib.auth.models import User
    user = User.objects.get(username='cicero_guest')
  topic.article_set.create(
    text=data['text'], 
    author=user,
    guest_name=data['name'],
    filter=user.cicero_profile.filter,
  )
  
def _validate_name(user, data):
  if user.is_authenticated():
    return u''
  else:
    if not data['name']:
      raise ValidationError('Обязательное поле')
    return data['name']

class ArticleForm(Form):
  text = CharField(label='Текст', widget=Textarea(attrs={'cols': '80', 'rows': '20'}))
  name = CharField(label='Имя', required=False)
  
  def __init__(self, topic, user, *args, **kwargs):
    super(ArticleForm, self).__init__(*args, **kwargs)
    self.topic, self.user = topic, user
    
  def clean_name(self):
    return _validate_name(self.user, self.clean_data)
    
  def save(self):
    _create_article(self.topic, self.user, self.clean_data)
  
class TopicForm(Form):
  subject = CharField(label='Тема')
  text = CharField(label='Текст', widget=Textarea(attrs={'cols': '80', 'rows': '20'}))
  name = CharField(label='Имя', required=False)
  
  def __init__(self, forum, user, *args, **kwargs):
    super(TopicForm, self).__init__(*args, **kwargs)
    self.forum, self.user = forum, user
    
  def clean_name(self):
    return _validate_name(self.user, self.clean_data)
  
  def save(self):
    from cicero.models import Topic
    topic = Topic(forum=self.forum, subject=self.clean_data['subject'])
    topic.save()
    _create_article(topic, self.user, self.clean_data)

class AuthForm(Form):
  openid = URLField(label='OpenID', required=True)
  
  def __init__(self, session, *args, **kwargs):
    Form.__init__(self, *args, **kwargs)
    self.session = session
    
  def _site_url(self):
    from django.contrib.sites.models import Site
    site = Site.objects.get_current()
    return 'http://' + site.domain
  
  def clean_openid(self):
    from cicero.auth import get_consumer
    from yadis.discover import DiscoveryFailure
    from urljr.fetchers import HTTPFetchingError
    consumer = get_consumer(self.session)
    errors = []
    try:
      self.request = consumer.begin(self.clean_data['openid'])
    except HTTPFetchingError, e:
      errors.append(str(e.why))
    except DiscoveryFailure, e:
      errors.append(str(e[0]))
    if hasattr(self, 'request') and self.request is None:
      errors.append('OpenID сервис не найден')
    if errors:
      raise ValidationError(errors)
    
  def auth_redirect(self, target):
    from django.core.urlresolvers import reverse
    site_url = self._site_url()
    trust_url = settings.OPENID_TRUST_URL or (site_url + '/')
    return_to = site_url + reverse('cicero.views.auth')
    self.request.return_to_args['redirect'] = target
    return self.request.redirectURL(trust_url, return_to)