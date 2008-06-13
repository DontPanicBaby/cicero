# -*- coding:utf-8 -*-
from django import template
from django.conf import settings
from django.utils.html import escape

register=template.Library()

@register.inclusion_tag('cicero/paginator.html', takes_context=True)
def paginator(context):
  '''
  Выводит навигатор по страницам. Данные берет из контекста в том же
  виде, как их туда передает generic view "object_list".
  '''
  if 'query_dict' in context:
    query = context['query_dict'].copy()
    if 'page' in query:
      del query['page']
    query_string = query.urlencode() + '&'
    form_input_string = u''.join([u'<input type="hidden" name="%s" value="%s">' % (k, escape(v)) for k, l in query.lists() for v in l])
  else:
    query_string = u''
    form_input_string = u''
  return {
    'paginator': context['paginator'],
    'page': context['page_obj'],
    'query_string': query_string,
    'form_input_string': form_input_string,
    'show_last_link': context.get('show_last_link'),
  }
  
@register.simple_tag
def obj_url(obj):
  from django.core.urlresolvers import RegexURLResolver, NoReverseMatch, reverse_helper
  
  def find_object_url(resolver, obj):
    for pattern in resolver.urlconf_module.urlpatterns:
      if isinstance(pattern, RegexURLResolver):
        try:
          return reverse_helper(pattern.regex) + find_object_url(pattern, obj)
        except NoReverseMatch:
          continue
      elif pattern.callback.__name__ == 'object_detail':
        queryset = pattern.default_args['queryset']
        if isinstance(obj, queryset.model):
          return pattern.reverse_helper(obj._get_pk_val())
        else:
          continue
    raise NoReverseMatch
  
  resolver = RegexURLResolver(r'^/', settings.ROOT_URLCONF)
  try:
    return '/' + find_object_url(resolver, obj)
  except NoReverseMatch:
    return ''
    
class SetNewsNode(template.Node):
  def __init__(self, objects_expr):
    self.objects_expr = objects_expr

  def render(self, context):
    objects = self.objects_expr.resolve(context)
    if not context['profile'] or len(objects) == 0:
      return ''
    context['profile'].set_news(objects)
    return ''

@register.tag
def setnews(parser, token):
  bits = token.contents.split()
  if len(bits) != 2:
    raise template.TemplateSyntaxError, '"%s" takes object list as parameter ' % bits[0]
  return SetNewsNode(parser.compile_filter(bits[1]))

class IfCanChangeNode(template.Node):
  def __init__(self, profile_expr, article_expr, node_list):
    self.profile_expr, self.article_expr, self.node_list = profile_expr, article_expr, node_list
    
  def render(self, context):
    profile = self.profile_expr.resolve(context)
    article = self.article_expr.resolve(context)
    if profile and profile.can_change(article):
      return self.node_list.render(context)
    return ''

@register.tag
def ifcanchange(parser, token):
  '''
  Выводит содержимое блока только в том случае, если пользователь
  имеет право редактироват статью
  '''
  bits = token.contents.split()
  if len(bits) != 3:
    raise template.TemplateSyntaxError, '"%s" принимает 2 параметра: профиль и статью' % bits[0]
  node_list = parser.parse('end' + bits[0])
  parser.delete_first_token()
  return IfCanChangeNode(parser.compile_filter(bits[1]), parser.compile_filter(bits[2]), node_list)