# -*- coding:utf-8 -*-
from django.core.urlresolvers import reverse
from django.contrib.sites.models import Site
from django.conf import settings

from cicero.utils import akismet

def _forum_url(view_name, *args, **kwargs):
  domain = Site.objects.get_current().domain
  return 'http://%s%s' % (domain, reverse(view_name, *args, **kwargs))

def _article_data(request, article, is_new_topic):
  text = article.text
  if is_new_topic:
    text = article.topic.subject + '\n' + text
  return {
    'key': settings.AKISMET_KEY, 
    'blog': _forum_url('cicero_index'), 
    'user_ip': article.ip,
    'user_agent': request.META['HTTP_USER_AGENT'],
    'referrer': request.META['HTTP_REFERER'],
    'permalink': _forum_url('cicero.views.topic', args=[article.topic.forum.slug, article.topic.id]),
    'comment_type': 'post',
    'comment_author': article.from_guest() and article.guest_name.encode('utf-8') or str(article.author.cicero_profile),
    'comment_author_url': article.author.cicero_profile.openid or '',
    'comment_content': text.encode('utf-8'),
    'HTTP_ACCEPT': request.META['HTTP_ACCEPT'],
  }

def _create_operation(operation):
  def func(request, article, is_new_topic):
    if not akismet.verify_key(settings.AKISMET_KEY, _forum_url('cicero_index')):
      raise Exception('Invalid Akismet key')
    return getattr(akismet, operation)(**_article_data(request, article, is_new_topic))
  return func

comment_check = _create_operation('comment_check')
submit_spam = _create_operation('submit_spam')
submit_ham = _create_operation('submit_ham')