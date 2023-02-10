from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase

from ..models import Group, Post

User = get_user_model()


class StaticURLTests(TestCase):
    def test_homepage(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_about_author(self):
        response = self.client.get('/about/author/')
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_about_tech(self):
        response = self.client.get('/about/tech/')
        self.assertEqual(response.status_code, HTTPStatus.OK)


class PostsURLTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='Автор')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост',
        )

    def setUp(self):
        self.user_no_author = User.objects.create_user(username='HasNoName')
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user_no_author)
        self.authorized_client_author = Client()
        self.authorized_client_author.force_login(self.user)
        cache.clear()

    def test_home_url_exists_at_desired_location(self):
        """Страницы доступны"""
        pages = {'/': self.client,
                 f'/group/{self.group.slug}/': self.client,
                 f'/profile/{self.user_no_author}/': self.client,
                 f'/posts/{self.post.pk}/': self.client,
                 '/create/': self.authorized_client,
                 f'/posts/{self.post.pk}/edit/': self.authorized_client_author,
                 }

        for page, client in pages.items():
            with self.subTest(page):
                response = client.get(page)
                self.assertEqual(response.status_code, HTTPStatus.OK,
                                 f'Страница {page} не найдена')

    def test_inexisting_page_url_exists_at_desired_location(self):
        """Страница /unexisting_page/ не существует."""
        response = self.client.get('/unexisting_page/')
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_posts_id_edit_url_redirect_anonymous(self):
        """Страница /posts/<post_id>/edit/ перенаправляет
        анонимного пользователя."""
        response = self.client.get(
            f'/posts/{self.post.pk}/edit/', follow=True)
        self.assertRedirects(
            response, f'/auth/login/?next=/posts/{self.post.pk}/edit/')

    def test_create_url_redirect_anonymous(self):
        """Страница /create/ перенаправляет анонимного
        пользователя."""
        response = self.client.get('/create/', follow=True)
        self.assertRedirects(response, '/auth/login/?next=/create/')

    def test_urls_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        templates_url_names = {
            '/': 'posts/index.html',
            f'/group/{self.group.slug}/': 'posts/group_list.html',
            f'/profile/{self.user}/': 'posts/profile.html',
            f'/posts/{self.post.pk}/': 'posts/post_detail.html',
            '/unexisting_page/': 'core/404.html',
        }
        for address, template in templates_url_names.items():
            with self.subTest(address=address):
                response = self.authorized_client.get(address)
                self.assertTemplateUsed(response, template)
