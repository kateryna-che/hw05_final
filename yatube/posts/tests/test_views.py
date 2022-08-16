import shutil
import tempfile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from ..forms import PostForm
from ..models import Follow, Group, Post

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)
User = get_user_model()


class TaskPagesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )
        cls.user = User.objects.create_user(username='auth')
        cls.follow = User.objects.create_user(username='foll')
        cls.unfollow = User.objects.create_user(username='unfoll')
        cls.group = Group.objects.create(
            title='test-group',
            slug='test-slug',
            description='test-description',
        )
        cls.group_without_posts = Group.objects.create(
            title='test-group-without-posts',
            slug='test-slug-without-posts',
            description='test-description-without-posts',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='test-post',
            group=cls.group,
            image=uploaded,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)
        cache.clear()

    def setUp(self):
        self.unauthorized_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        cache.clear()

    def post_attributes_test(self, response, bull=False):
        if bull:
            post = response.context.get('post')
        else:
            post = response.context['page_obj'][0]
        post_attributes = {
            post.id: self.post.id,
            post.text: self.post.text,
            post.author: self.post.author,
            post.group: self.post.group,
            post.image: self.post.image,
        }
        for test_attribute, attribute in post_attributes.items():
            with self.subTest(attribute=test_attribute):
                self.assertEqual(test_attribute, attribute)

    def test_pages_uses_correct_template(self):
        templates_pages_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse('posts:profile', kwargs={'username': self.user}):
                'posts/profile.html',
            reverse('posts:group_list', kwargs={'slug': self.group.slug}):
                'posts/group_list.html',
            reverse('posts:post_detail',
                    kwargs={'post_id': self.post.id}):
                'posts/post_detail.html',
            reverse('posts:post_edit',
                    kwargs={'post_id': self.post.id}):
                'posts/create_post.html',
            reverse('posts:post_create'): 'posts/create_post.html',
            reverse('posts:follow_index'): 'posts/follow.html',
        }
        for reverse_name, template in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_post_index_show_correct_context(self):
        response = self.authorized_client.get(reverse('posts:index'))
        self.post_attributes_test(response)

    def test_post_group_list_show_correct_context(self):
        response = self.authorized_client.get(reverse(
            'posts:group_list',
            kwargs={'slug': self.post.group.slug})
        )
        self.assertEqual(response.context['group'], self.post.group)
        self.post_attributes_test(response)

    def test_post_profile_show_correct_context(self):
        response = self.authorized_client.get(reverse(
            'posts:profile',
            kwargs={'username': self.post.author})
        )
        self.assertEqual(response.context['author'], self.post.author)
        self.post_attributes_test(response)

    def test_post_detail_show_correct_context(self):
        response = self.authorized_client.get(reverse(
            'posts:post_detail',
            kwargs={'post_id': self.post.id})
        )
        self.post_attributes_test(response, True)

    def test_post_edit_show_correct_context(self):
        response = self.authorized_client.get(reverse(
            'posts:post_edit',
            kwargs={'post_id': self.post.id})
        )
        self.assertIsInstance(response.context.get('form'), PostForm)

    def test_post_create_show_correct_context(self):
        response = self.authorized_client.get(reverse('posts:post_create'))
        self.assertIsInstance(response.context.get('form'), PostForm)

    def test_creating_post(self):
        self.assertNotEqual(self.post.group, self.group_without_posts)

    def test_index_cash(self):
        response = self.authorized_client.get(reverse('posts:index'))
        posts = response.content
        Post.objects.create(
            author=self.user,
            text='test-post',
        )
        response_old = self.authorized_client.get(reverse('posts:index'))
        posts_old = response_old.content
        self.assertEqual(posts, posts_old)
        cache.clear()
        response_new = self.authorized_client.get(reverse('posts:index'))
        posts_new = response_new.content
        self.assertNotEqual(posts_new, posts_old)

    def test_follow_index(self):
        Follow.objects.create(user=self.user, author=self.follow)
        response = self.authorized_client.get(reverse('posts:follow_index'))
        follow_posts = len(response.context['page_obj'])
        Post.objects.create(
            author=self.unfollow,
            text='test-post',
        )
        response_new = self.authorized_client.get(
            reverse('posts:follow_index')
        )
        self.assertEqual(len(response_new.context['page_obj']), follow_posts)

    def test_profile_follow_unfollow(self):
        self.authorized_client.get(reverse(
            'posts:profile_follow',
            kwargs={'username': self.follow})
        )
        follow = Follow.objects.filter(
            user=self.user,
            author=self.follow
        ).count()
        self.assertEqual(follow, 1)
        self.authorized_client.get(reverse(
            'posts:profile_unfollow',
            kwargs={'username': self.follow})
        )
        follow = Follow.objects.filter(
            user=self.user,
            author=self.follow
        ).count()
        self.assertEqual(follow, 0)


class PaginatorViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_paginator = User.objects.create_user(
            username='user-paginator'
        )
        cls.author = User.objects.create_user(
            username='follower'
        )
        cls.group = Group.objects.create(
            title='test-group',
            slug='test-slug',
            description='test-description',
        )
        Post.objects.bulk_create([
            Post(
                author=cls.author,
                text='test-post',
                group=cls.group
            )
            for i in range(13)
        ])
        Follow.objects.create(user=cls.user_paginator, author=cls.author)

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user_paginator)

    def test_paginator(self):
        pages = {
            'posts:index': '',
            'posts:group_list': {'slug': self.group.slug},
            'posts:profile': {'username': self.author},
            'posts:follow_index': '',
        }
        for page, kwargs in pages.items():
            with self.subTest(page=page):
                pages_num = {'1': 10, '2': 3}
                for num, posts in pages_num.items():
                    response = self.client.get(
                        reverse(page, kwargs=kwargs) + f'?page={num}'
                    )
                    self.assertEqual(len(response.context['page_obj']), posts)
