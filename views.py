# -*- coding:utf-8 -*-
from django.views.generic.list_detail import object_list
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden
from django.conf import settings

from cicero.models import Forum, Topic
from cicero.forms import ArticleForm, TopicForm, AuthForm

def render_to_response(request, template_name, context_dict):
  from cicero.context import default
  from django.template import RequestContext
  from django.shortcuts import render_to_response as _render_to_response
  context = RequestContext(request, context_dict, [default])
  return _render_to_response(template_name, context_instance=context)
  
def post_redirect(request):
  return request.POST.get('redirect', request.META.get('HTTP_REFERER', '/'))
  
def own_profile(func):
  def wrapper(request, *args, **kwargs):
    if not request.user.is_authenticated():
      from django.core.urlresolvers import reverse
      return HttpResponseRedirect(reverse(login) + '?redirect=' + request.path)
    return func(request, *args, **kwargs)
  return wrapper

def forum(request, slug, **kwargs):
  forum = get_object_or_404(Forum, slug=slug)
  if request.method == 'POST':
    form = TopicForm(forum, request.user, request.POST)
    if form.is_valid():
      form.save()
      return HttpResponseRedirect('./')
  else:
    form = TopicForm(forum, request.user)
  kwargs['queryset'] = forum.topic_set.all()
  kwargs['extra_context'] = {'forum': forum, 'form': form, 'page_id': 'forum'}
  return object_list(request, **kwargs)

def topic(request, slug, id, **kwargs):
  topic = get_object_or_404(Topic, forum__slug=slug, pk=id)
  if request.method == 'POST':
    form = ArticleForm(topic, request.user, request.POST)
    if form.is_valid():
      form.save()
      return HttpResponseRedirect('./?page=last')
  else:
    form = ArticleForm(topic, request.user)
  if request.GET.get('page', '') == 'last':
    count = topic.article_set.count()
    page = count / settings.PAGINATE_BY
    if count % settings.PAGINATE_BY:
      page += 1
    return HttpResponseRedirect(page > 1 and './?page=%s' % page or './')
  kwargs['queryset'] = topic.article_set.all()
  kwargs['extra_context'] = {'topic': topic, 'form': form, 'page_id': 'topic'}
  return object_list(request, **kwargs)
  
def login(request):
  if request.method == 'POST':
    form = AuthForm(request.session, request.POST)
    if form.is_valid():
      after_auth_redirect = form.auth_redirect(post_redirect(request), 'cicero.views.auth')
      return HttpResponseRedirect(after_auth_redirect)
    redirect = post_redirect(request)
  else:
    form = AuthForm(request.session)
    redirect = request.GET.get('redirect', '/')
  return render_to_response(request, 'cicero/login.html', {'form': form, 'redirect': redirect})
    
def auth(request):
  from django.contrib.auth import authenticate, login
  user = authenticate(session=request.session, query=request.GET)
  if not user:
    return HttpResponseForbidden('Ошибка авторизации')
  login(request, user)
  return HttpResponseRedirect(request.GET.get('redirect', '/'))
  
@require_http_methods('POST')
def logout(request):
  from django.contrib.auth import logout
  logout(request)
  return HttpResponseRedirect(post_redirect(request))
  
@own_profile
def edit_profile(request):
  from cicero.forms import AuthForm, PersonalForm, SettingsForm
  profile = request.user.cicero_profile
  forms = {
    'openid_form': AuthForm(request.session, initial={'openid_url': profile.openid}),
    'personal_form': PersonalForm(profile, initial=profile.__dict__),
    'settings_form': SettingsForm(profile, initial=profile.__dict__),
  }
  if request.method == 'POST':
    try:
      form_name = request.POST['form'] + '_form'
      if form_name == 'openid_form':
        form = forms[form_name].__class__(request.session, request.POST)
      else:
        form = forms[form_name].__class__(profile, request.POST)
      forms[form_name] = form
    except KeyError:
      response = HttpResponse('Unknown action')
      response.status_code = 501
      return response
    if form.is_valid():
      if form_name == 'openid_form':
        after_auth_redirect = form.auth_redirect(post_redirect(request), 'cicero.views.change_openid_complete', request.user.id)
        return HttpResponseRedirect(after_auth_redirect)
      else:
        form.process()
        return HttpResponseRedirect('./')
  data = {'page_id': 'edit_profile'}
  data.update(forms)
  return render_to_response(request, 'cicero/profile_form.html', data)

@own_profile
def change_openid_complete(request):
  from django.contrib.auth import authenticate
  user = authenticate(session=request.session, query=request.GET)
  if not user:
    return HttpResponseForbidden('Ошибка авторизации')
  new_profile = user.cicero_profile
  profile = request.user.cicero_profile
  if profile != new_profile:
    profile.openid, profile.openid_server = new_profile.openid, new_profile.openid_server
    new_profile.delete()
    profile.save()
    for article in user.article_set.all():
      article.author = request.user
      article.save()
    user.delete()
    profile.generate_mutant()
  return HttpResponseRedirect(request.GET.get('redirect', '/'))
  
@own_profile
@require_http_methods('POST')
def read_hcard(request):
  profile = request.user.cicero_profile
  profile.read_hcard()
  profile.save()
  return HttpResponseRedirect('../')