from http import HTTPStatus
import pytest
from django.urls import reverse
from pytest_django.asserts import assertRedirects
from news.models import Comment, News
from django.contrib.auth import get_user_model

# Получаем модель пользователя
User = get_user_model()


@pytest.fixture
def news():
    return News.objects.create(title='Заголовок', text='Текст')


@pytest.fixture
def author():
    return User.objects.create(username='Лев Толстой')


@pytest.fixture
def reader():
    return User.objects.create(username='Читатель простой')


@pytest.fixture
def comment(news, author):
    return Comment.objects.create(news=news, author=author, text='Текст комментария')


@pytest.mark.django_db
@pytest.mark.parametrize(
    'name, args',
    (
            ('news:home', None),
            ('news:detail', None),
            ('users:login', None),
            ('users:logout', None),
            ('users:signup', None),
    )
)
# Тестируем доступность страниц
def test_pages_availability(client, name, args, news):
    if name == 'news:detail':
        # Передаем id новости из фикстуры
        args = (news.id,)
    url = reverse(name, args=args)
    if name == 'users:logout':
        response = client.post(url)  # Используем POST для logout
    else:
        response = client.get(url)  # Для других страниц GET
    assert response.status_code == HTTPStatus.OK


@pytest.mark.django_db
@pytest.mark.parametrize(
    'user, expected_status',
    (
        ('author', HTTPStatus.OK),
        ('reader', HTTPStatus.NOT_FOUND),
    )
)
# Тестируем доступность редактирования и удаления комментариев
def test_availability_for_comment_edit_and_delete(client, user, expected_status, author, reader, comment):
    user_instance = author if user == 'author' else reader
    client.force_login(user_instance)

    for name in ('news:edit', 'news:delete'):
        url = reverse(name, args=(comment.id,))
        response = client.get(url)
        assert response.status_code == expected_status



@pytest.mark.django_db
@pytest.mark.parametrize(
    'name',
    ('news:edit', 'news:delete')
)
# Тестируем редирект для анонимного пользователя
def test_redirect_for_anonymous_client(client, name, comment):
    login_url = reverse('users:login')
    url = reverse(name, args=(comment.id,))
    redirect_url = f'{login_url}?next={url}'

    response = client.get(url)
    assertRedirects(response, redirect_url)
