# -*- coding:utf-8 -*-
from django.contrib.syndication.feeds import Feed, FeedDoesNotExist
from django.utils.feedgenerator import Atom1Feed
from django.core.urlresolvers import reverse
from django.conf import settings

from cicero import models

class Article(Feed):
  feed_type = Atom1Feed
  
  def get_object(self, bits):
    if len(bits) == 1:
      return models.Forum.objects.get(slug=bits[0])
    if len(bits) == 2:
      return models.Topic.objects.get(forum__slug=bits[0], id=int(bits[1]))
    raise FeedDoesNotExist
  
  def title(self, obj):
    return unicode(obj)
  
  def link(self, obj):
    return obj.get_absolute_url()
  
  def item_link(self, article):
    return reverse('cicero.views.topic', args=[article.topic.forum.slug, article.topic.id])
  
  def items(self, obj):
    if isinstance(obj, models.Forum):
      articles = models.Article.objects.filter(topic__forum=obj)
    elif isinstance(obj, models.Topic):
      articles = obj.article_set.all()
    return articles.filter(spam_status='clean').order_by('-created')[:settings.PAGINATE_BY]