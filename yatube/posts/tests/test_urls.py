from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from ..models import Group, Post

User = get_user_model()


class StaticURLTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.auth = User.objects.create_user(username='auth')
        cls.user = User.objects.create_user(username='user')
        cls.group = Group.objects.create(
            title='test-group',
            slug='test-slug',
            description='test-description',
        )
        cls.post = Post.objects.create(
            author=cls.auth,
            text='test-post',
        )

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.auth)
        self.authorized_no_auth = Client()
        self.authorized_no_auth.force_login(self.user)
        cache.clear()

    def test_urls_uses_correct_template(self):
        templates_url_names = {
            '/': 'posts/index.html',
            f'/group/{self.group.slug}/': 'posts/group_list.html',
            f'/profile/{self.user}/': 'posts/profile.html',
            f'/posts/{self.post.id}/': 'posts/post_detail.html',
            f'/posts/{self.post.id}/edit/': 'posts/create_post.html',
            '/create/': 'posts/create_post.html',
            '/follow/': 'posts/follow.html',

        }
        for address, template in templates_url_names.items():
            with self.subTest(address=address):
                response = self.authorized_client.get(address)
                self.assertTemplateUsed(response, template)

    def test_pages(self):
        url_names = (
            '/',
            f'/group/{self.group.slug}/',
            f'/profile/{self.auth}/',
            f'/posts/{self.post.id}/',
            f'/posts/{self.post.id}/edit/',
            '/create/',
        )
        for url in url_names:
            with self.subTest(url=url):
                response = self.authorized_client.get(url)
                self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_redirect_no_auth(self):
        response = self.authorized_no_auth.get(f'/posts/{self.post.pk}/edit/')
        self.assertRedirects(response, f'/posts/{self.post.pk}/')

    def test_redirect_unauthorized(self):
        urls = {
            f'/posts/{self.post.pk}/edit/':
                f'/auth/login/?next=/posts/{self.post.pk}/edit/',
            '/create/': '/auth/login/?next=/create/',
        }
        for url, redirect in urls.items():
            with self.subTest(url=url):
                self.assertRedirects(self.guest_client.get(url), redirect)
