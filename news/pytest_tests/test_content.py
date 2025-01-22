import pytest
from datetime import datetime, timedelta
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.test import Client
from news.models import Comment, News
from news.forms import CommentForm
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.fixture
def create_news():
    today = datetime.today()
    all_news = [
        News(
            title=f'Новость {index}',
            text='Просто текст.',
            date=today - timedelta(days=index)
        )
        for index in range(settings.NEWS_COUNT_ON_HOME_PAGE + 1)
    ]
    News.objects.bulk_create(all_news)

@pytest.fixture
def create_comments(create_news):
    # Удаляем пользователя с таким именем, если он уже существует
    User.objects.filter(username='Комментатор').delete()

    # Создаём нового пользователя
    author = User.objects.create_user(username='Комментатор', password='password')

    news = News.objects.first()
    now = timezone.now()
    for index in range(10):
        comment = Comment.objects.create(
            news=news, author=author, text=f'Tекст {index}',
        )
        comment.created = now + timedelta(days=index)
        comment.save()
    return news

@pytest.fixture
def client_with_author(create_comments):
    # Создаём пользователя с именем 'Комментатор', если он ещё не был создан
    author = User.objects.get(username='Комментатор')
    client = Client()
    client.force_login(author)
    return client

@pytest.mark.django_db
def test_news_count(client, create_news):
    home_url = reverse('news:home')
    response = client.get(home_url)
    object_list = response.context['object_list']
    news_count = object_list.count()
    assert news_count == settings.NEWS_COUNT_ON_HOME_PAGE

@pytest.mark.django_db
def test_news_order(client, create_news):
    home_url = reverse('news:home')
    response = client.get(home_url)
    object_list = response.context['object_list']
    all_dates = [news.date for news in object_list]
    sorted_dates = sorted(all_dates, reverse=True)
    assert all_dates == sorted_dates

@pytest.mark.django_db
def test_comments_order(client, create_comments):
    detail_url = reverse('news:detail', args=(create_comments.id,))
    response = client.get(detail_url)
    news = response.context['news']
    all_comments = news.comment_set.all()
    all_timestamps = [comment.created for comment in all_comments]
    sorted_timestamps = sorted(all_timestamps)
    assert all_timestamps == sorted_timestamps

@pytest.mark.django_db
def test_anonymous_client_has_no_form(client, create_comments):
    detail_url = reverse('news:detail', args=(create_comments.id,))
    response = client.get(detail_url)
    assert 'form' not in response.context

@pytest.mark.django_db
def test_authorized_client_has_form(client_with_author, create_comments):
    detail_url = reverse('news:detail', args=(create_comments.id,))
    response = client_with_author.get(detail_url)
    assert 'form' in response.context
    assert isinstance(response.context['form'], CommentForm)


@pytest.mark.parametrize(
    'user, expected_status',
    (
        ('author', 200),  # Авторизованный клиент
        ('reader', 403),  # Неавторизованный клиент
    )
)
@pytest.mark.django_db
def test_comment_creation_form_availability(client, user, expected_status, create_comments):
    # Создание пользователя
    user_instance = User.objects.create_user(username=user, password='password') if user == 'reader' else User.objects.get(username='Комментатор')
    client.force_login(user_instance)

    # Получение страницы с новостью
    detail_url = reverse('news:detail', args=(create_comments.id,))
    response = client.get(detail_url)

    # Проверка доступности формы для авторизованного пользователя
    if expected_status == 200:
        # Для авторизованного пользователя форма должна быть в контексте
        assert 'form' in response.context
        assert isinstance(response.context['form'], CommentForm)

        # Проверяем, что форма не привязана (is_bound == False)
        assert not response.context['form'].is_bound  # Форма не привязана до отправки данных

        # Проверяем, что форма невалидна до отправки данных
        assert not response.context['form'].is_valid()

        # Проверка отправки формы с данными (POST запрос)
        form_data = {'text': 'Новый комментарий'}
        response = client.post(detail_url, data=form_data)

        # После успешного добавления комментария перенаправление должно быть на страницу новости
        assert response.status_code == 302
        assert Comment.objects.filter(text='Новый комментарий').exists()

    else:
        # Для неавторизованного пользователя формы не должно быть в контексте
        assert 'form' not in response.context or not response.context['form'].is_bound
