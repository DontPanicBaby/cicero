# -*- coding:utf-8 -*-
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from cicero.fields import AutoOneToOneField

class Forum(models.Model):
  slug = models.SlugField()
  name = models.CharField(maxlength=255)
  group = models.CharField(maxlength=255, blank=True)
  ordering = models.IntegerField(default=0)
  
  class Meta:
    ordering = ['ordering', 'group']
  
  class Admin:
    list_display = ['name', 'ordering', 'group']
  
  def __str__(self):
    return self.name
    
class Topic(models.Model):
  forum = models.ForeignKey(Forum)
  subject = models.CharField(maxlength=255)
  created = models.DateTimeField(auto_now_add=True)
  
  class Meta:
    ordering = ['-id']
    
  class Admin:
    pass
  
  def __str__(self):
    return self.subject
    
class ArticleManager(models.Manager):
  def get_query_set(self):
    return super(ArticleManager, self).get_query_set().select_related()
    
class Article(models.Model):
  topic = models.ForeignKey(Topic)
  text = models.TextField()
  filter = models.CharField(maxlength=50)
  created = models.DateTimeField(auto_now_add=True)
  author = models.ForeignKey(User)
  guest_name = models.CharField(maxlength=255, blank=True)
  
  objects = ArticleManager()
  
  class Meta:
    ordering = ['id']
    
  class Admin:
    pass
  
  def __str__(self):
    return '(%s, %s, %s)' % (self.topic, self.author, self.created.replace(microsecond=0))
    
  def html(self):
    '''
    Возвращает HTML-текст статьи, полученный фильтрацией содержимого
    через указанный фильтр.
    '''
    from cicero.filters import filters
    if self.filter in filters:
      result = filters[self.filter](self.text)
    else:
      from django.utils.html import linebreaks, escape
      result = linebreaks(escape(self.text))
    import re
    result = re.sub(r'\B--\B', '—', result)
    return result
    
  def author_display(self):
    '''
    Имя автора статьи для отображения. Берется из имени автора, если он
    не гость, либо из отдельного поля имени гостя.
    '''
    return self.author.username != 'cicero_guest' and self.author.cicero_profile or self.guest_name

class Profile(models.Model):
  user = AutoOneToOneField(User, related_name='cicero_profile')
  filter = models.CharField(maxlength=50)
  openid = models.URLField(null=True, verify_exists=False, unique=True)
  name = models.CharField(maxlength=200, null=True)
  
  class Admin:
    pass
  
  def __str__(self):
    if self.name:
      return self.name
    elif self.openid:
      result = self.openid[self.openid.index('://') + 3:]
      try:
        if result.index('/') == len(result) - 1:
          result = result[:-1]
      except ValueError:
        pass
      return result
    else:
      return str(self.user)
      
  def update_name(self):
    '''
    Ищет на странице, на которую указывает openid, микроформамт hCard,
    и берет оттуда имя, если есть.
    '''
    from urllib2 import urlopen, URLError
    try:
      file = urlopen(self.openid)
      content = file.read(512 * 1024)
    except (URLError, IOError):
      pass
    import re
    from BeautifulSoup import BeautifulSoup
    soup = BeautifulSoup(content)
    vcard = soup.find(None, {'class': re.compile(r'\bvcard\b')})
    if vcard is None:
      return
      
    def _parse_property(class_name):
      el = vcard.find(None, {'class': re.compile(r'\b%s\b' % class_name)})
      if el is None:
        return
      if el.name == u'abbr' and el['title']:
        return el['title'].strip().encode(settings.DEFAULT_CHARSET)
      else:
        result = ''.join([s for s in el.recursiveChildGenerator() if isinstance(s, unicode)])
        return result.strip().encode(settings.DEFAULT_CHARSET)
        
    info = dict((n, _parse_property(n)) for n in ['nickname', 'fn'])
    self.name = info['nickname'] or info['fn']
    
  def save(self):
    if not self.filter:
      self.filter = 'bbcode'
    if self.openid and not self.name:
      self.update_name()
    super(Profile, self).save()
