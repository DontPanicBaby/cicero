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
    
from django.db.models.query import QuerySet
class ArticleQuerySet(QuerySet):
  def _get_data(self):
    update_profiles = self._result_cache is None and self._select_related
    if update_profiles:
      profile_select = dict((f.attname, Profile._meta.db_table + '.' + f.attname) for f in Profile._meta.fields)
      self._select.update(profile_select)
      self._tables.extend([Profile._meta.db_table])
      self._where.extend(['%s.%s = %s.%s' % (Profile._meta.db_table, Profile._meta.pk.attname, User._meta.db_table, User._meta.pk.attname)])
    result = super(ArticleQuerySet, self)._get_data()
    if update_profiles:
      for article in result:
        data = dict((f.attname, getattr(article, f.attname)) for f in Profile._meta.fields)
        article.cicero_profile = Profile(**data)
    return result

class ArticleManager(models.Manager):
  def get_query_set(self):
    return ArticleQuerySet(self.model).select_related()
    
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
    
  def from_guest(self):
    '''
    Была ли написана статья от имени гостя. Используется, в основном,
    в шаблонах.
    '''
    return self.author.username == 'cicero_guest'

class Profile(models.Model):
  user = AutoOneToOneField(User, related_name='cicero_profile')
  filter = models.CharField(maxlength=50)
  openid = models.CharField(maxlength=200, null=True, unique=True)
  openid_server = models.CharField(maxlength=200, null=True)
  mutant = models.ImageField(upload_to='mutants', null=True)
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
      return
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
    
  def generate_mutant(self):
    '''
    Создает, если возможно, картинку мутанта из OpenID.
    '''
    import os
    if os.path.exists(self.get_mutant_filename()):
      os.remove(self.get_mutant_filename())
    if not settings.OPENID_MUTANT_PARTS or not self.openid or not self.openid_server:
      return
    from cicero.mutants import mutant
    from StringIO import StringIO
    content = StringIO()
    mutant(self.openid, self.openid_server).save(content, 'PNG')
    self.save_mutant_file('%s.png' % self._get_pk_val(), content.getvalue())