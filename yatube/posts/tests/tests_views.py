import shutil
import tempfile

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import Follow, Group, Post

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostPagesTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='Автор')
        cls.user_follower = User.objects.create_user(username='Подписчик')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        cls.uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост',
            group=cls.group,
            image=cls.uploaded
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.authorized_client = Client()
        self.authorized_client_author = Client()
        self.authorized_client_author.force_login(self.user)
        self.authorized_client.force_login(self.user_follower)

    def test_pages_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        templates_page_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse(
                'posts:group_list', kwargs={'slug': self.group.slug}
            ): 'posts/group_list.html',
            reverse(
                'posts:profile', kwargs={'username': self.user}
            ): 'posts/profile.html',
            reverse(
                'posts:post_detail', kwargs={'post_id': self.post.pk}
            ): 'posts/post_detail.html',
            reverse('posts:post_create'): 'posts/create_post.html',
            reverse(
                'posts:post_edit', kwargs={'post_id': self.post.pk}
            ): 'posts/create_post.html',
        }
        for reverse_name, template in templates_page_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client_author.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def check_fields(self, response):
        first_object = response.context['page_obj'][0]
        post_author_0 = first_object.author
        post_text_0 = first_object.text
        post_id_0 = first_object.pk
        post_group_id_0 = first_object.group.pk
        post_author_pk_0 = first_object.author.pk
        post_image_0 = first_object.image
        self.assertEqual(post_author_0, self.user)
        self.assertEqual(post_text_0, self.post.text)
        self.assertEqual(post_id_0, self.post.pk)
        self.assertEqual(post_group_id_0, self.group.pk)
        self.assertEqual(post_author_pk_0, self.user.pk)
        self.assertEqual(post_image_0, self.post.image)

    def test_index_page_show_correct_context(self):
        """Шаблон index сформирован с правильным контекстом."""
        response = self.client.get(reverse('posts:index'))
        self.check_fields(response)

    def test_group_list_page_show_correct_context(self):
        """Шаблон group_list сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse('posts:group_list', kwargs={'slug': self.group.slug}))
        self.check_fields(response)

    def test_profile_page_show_correct_context(self):
        """Шаблон profile сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse('posts:profile', kwargs={'username': self.user}))
        self.check_fields(response)

    def test_post_detail_page_show_correct_context(self):
        """Шаблон post_detail сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse('posts:post_detail', kwargs={'post_id': self.post.pk}))
        first_object = response.context['post']
        self.assertEqual(first_object.image, self.post.image)

    def test_create_post_page_show_correct_context(self):
        response = self.authorized_client_author.get(
            reverse('posts:post_create'))
        form_fields = {
            'text': forms.CharField,
            'group': forms.ChoiceField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)

    def test_post_edit_show_correct_context(self):
        """Шаблон post_edit сформирован с правильным контекстом."""
        response = self.authorized_client_author.get(
            reverse('posts:post_edit', kwargs={'post_id': self.post.pk})
        )
        form_fields = {
            "text": forms.fields.CharField,
            "group": forms.fields.ChoiceField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)

    def test_new_post_correct_group(self):
        """Пост появился на index, group_list, profile,
        и  отсутствует в другой группе."""
        Group.objects.create(
            title='Тестовая группа другая',
            slug='test-another',
            description='Тестовое описание другой группы',
        )
        pages = [
            reverse('posts:index'),
            reverse(
                'posts:group_list', kwargs={'slug': self.group.slug}),
            reverse(
                'posts:profile', kwargs={'username': self.post.author}),
            reverse(
                'posts:group_list', kwargs={'slug': 'test-another'})
        ]
        form_fields = dict.fromkeys(pages, Post.objects.get(
                                    group=self.post.group))
        for reverse_name, expected in form_fields.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                form_field = response.context['page_obj']
                if reverse_name == reverse(
                        'posts:group_list', kwargs={'slug': 'test-another'}):
                    self.assertNotIn(expected, form_field)
                else:
                    self.assertIn(expected, form_field)

    def test_authorized_user_can_follow(self):
        """Авторизованный пользователь может подписаться."""
        author = User.objects.get(username=self.user)
        follow_count = Follow.objects.count()
        self.authorized_client.get(
            reverse(
                'posts:profile_follow', kwargs={'username': author})
        )
        self.assertEqual(Follow.objects.count(), follow_count + 1)
        self.assertTrue(Follow.objects.filter(
            author=author,
            user=self.user_follower
        ).exists())

    def test_authorized_user_can_unfollow(self):
        """Авторизованный пользователь может отписаться."""
        author = User.objects.get(username=self.user)
        Follow.objects.create(
            author=author,
            user=self.user_follower
        )
        self.authorized_client.get(
            reverse(
                'posts:profile_unfollow', kwargs={'username': author})
        )
        self.assertFalse(Follow.objects.filter(
            author=author,
            user=self.user_follower
        ).exists())

    def test_unauthorized_user_cannot_follow(self):
        """Неавторизованный пользователь не может подписаться."""
        author = User.objects.get(username=self.user)
        follow_count = Follow.objects.count()
        self.client.get(
            reverse(
                'posts:profile_follow', kwargs={'username': author})
        )
        self.assertEqual(Follow.objects.count(), follow_count)

    def test_authorized_user_cannot_follow_himself(self):
        """Автор не может подписаться на самого себя."""
        author = User.objects.get(username=self.user)
        follow_count = Follow.objects.count()
        self.authorized_client_author.get(
            reverse(
                'posts:profile_follow', kwargs={'username': author})
        )
        self.assertEqual(Follow.objects.count(), follow_count)

    def test_cache_if_post_delete(self):
        """При удалении поста содержимое не меняется.
        При очистке кэша содержимое изменяется."""
        post = Post.objects.get(pk=self.post.pk)
        response = self.authorized_client.get(reverse('posts:index'))
        post.delete()
        response_before = self.authorized_client.get(reverse('posts:index'))
        self.assertEqual(response.content, response_before.content)
        cache.clear()
        response_after = self.authorized_client.get(reverse('posts:index'))
        self.assertNotEqual(response.content, response_after.content)


class PaginatorViewsTest(TestCase):
    NUM_CREATE_POSTS = 13

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='HasNoName')
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        self.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        for i in range(self.NUM_CREATE_POSTS):
            Post.objects.create(
                text=f'Тестовый пост {i}',
                group=self.group,
                author=self.user)
        self.pages = {
            'posts:index': None,
            'posts:group_list': {'slug': self.group.slug},
            'posts:profile': {'username': self.user},
        }

    def test_first_page_contains_ten_records(self):
        """Пагинатор выводит на первой странице 10 постов"""
        for reverse_name, kwargs in self.pages.items():
            with self.subTest(reverse_name=reverse_name, kwargs=kwargs):
                response = self.client.get(reverse(
                    reverse_name, kwargs=kwargs))
                self.assertEqual(
                    len(response.context['page_obj']), settings.POST_ON_PAGE,
                    f'На странице {reverse_name} ошибка пагинатора')

    def test_second_page_contains_three_records(self):
        """Пагинатор выводит на второй странице 3 поста"""
        remaining_pages = self.NUM_CREATE_POSTS - settings.POST_ON_PAGE
        for reverse_name, kwargs in self.pages.items():
            with self.subTest(reverse_name=reverse_name, kwargs=kwargs):
                response = self.client.get(reverse(
                    reverse_name, kwargs=kwargs) + '?page=2')
                self.assertEqual(
                    len(response.context['page_obj']), remaining_pages,
                    f'На странице {reverse_name} ошибка пагинатора')
