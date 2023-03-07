import shutil
import tempfile

from http import HTTPStatus
from django.test import Client, TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.conf import settings
from django import forms
from django.core.cache import cache

from posts.models import Comment, Follow, Group, Post, User


TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostViewsTest(TestCase):
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
        cls.user = User.objects.create_user(username='user')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-group',
            description='Тестовое описание группы',
        )
        cls.post = Post.objects.create(
            text='Тестовый текст поста',
            author=cls.user,
            group=cls.group,
            image=uploaded,
        )
        cls.templates_pages_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse('posts:group_list', kwargs={
                'slug': cls.group.slug}): 'posts/group_list.html',
            reverse('posts:profile', kwargs={
                'username': cls.post.author.username}): 'posts/profile.html',
            reverse('posts:post_detail', kwargs={
                'post_id': cls.post.id}): 'posts/post_detail.html',
            reverse('posts:edit', kwargs={
                'post_id': cls.post.id}): 'posts/create_post.html',
            reverse('posts:create'): 'posts/create_post.html',
        }

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def check_post_info(self, post):
        """Информация о посте корректна."""
        with self.subTest(post=post):
            self.assertEqual(post.text, self.post.text)
            self.assertEqual(post.author, self.post.author)
            self.assertEqual(post.group.id, self.post.group.id)
            self.assertEqual(post.image, self.post.image)

    def test_pages_uses_correct_template(self):
        """Views-функции используют правильные html-шаблоны."""
        for reverse_name, template in self.templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_home_page_show_correct_context(self):
        """Сontext в шаблоне index.html соответствует ожиданиям."""
        response = self.authorized_client.get(reverse('posts:index'))
        self.check_post_info(response.context['page_obj'][0])

    def test_group_list_page_show_correct_context(self):
        """Сontext в шаблоне group_list.html соответствует ожиданиям."""
        response = self.authorized_client.get(reverse(
            'posts:group_list',
            kwargs={'slug': self.group.slug})
        )
        self.assertEqual(response.context['group'], self.group)
        self.check_post_info(response.context['page_obj'][0])

    def test_profile_page_show_correct_context(self):
        """Сontext в шаблоне profile.html соответствует ожиданиям."""
        response = self.authorized_client.get(reverse(
            'posts:profile', kwargs={'username': self.user.username})
        )
        self.assertEqual(response.context['author'], self.user)
        self.check_post_info(response.context['page_obj'][0])

    def test_post_detail_page_show_correct_context(self):
        """Сontext в шаблоне post_detail.html соответствует ожиданиям."""
        response = self.authorized_client.get(reverse(
            'posts:post_detail',
            kwargs={'post_id': self.post.id}))
        self.check_post_info(response.context['post'])

    def test_forms_for_create_posts(self):
        """Сontext в шаблоне create_post.html соответствует ожиданиям."""
        context = [
            reverse('posts:create'),
            reverse('posts:edit', kwargs={'post_id': self.post.id})
        ]
        for reverse_page in context:
            with self.subTest(reverse_page=reverse_page):
                response = self.authorized_client.get(reverse_page)
                self.assertIsInstance(
                    response.context['form'].fields['text'],
                    forms.fields.CharField)
                self.assertIsInstance(
                    response.context['form'].fields['group'],
                    forms.fields.ChoiceField)

    def test_showing_post_on_pages(self):
        """Проверка отображения поста на выделенных страницах."""
        form_fields = {
            reverse("posts:index"): Post.objects.get(group=self.post.group),
            reverse(
                "posts:group_list", kwargs={"slug": self.group.slug}
            ): Post.objects.get(group=self.post.group),
            reverse(
                "posts:profile", kwargs={"username": self.post.author}
            ): Post.objects.get(group=self.post.group),
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                response = self.authorized_client.get(value)
                form_field = response.context["page_obj"]
                self.assertIn(expected, form_field)

    def test_not_in_wrong_group(self):
        """Проверка, что пост в нужной группе."""
        form_fields = {
            reverse(
                "posts:group_list", kwargs={"slug": self.group.slug}
            ): Post.objects.exclude(group=self.post.group),
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                response = self.authorized_client.get(value)
                form_field = response.context["page_obj"]
                self.assertNotIn(expected, form_field)


class CacheTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='user')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-group',
            description='Тестовое описание группы',
        )
        cls.post = Post.objects.create(
            text='Тестовый текст поста',
            author=cls.user,
            group=cls.group,
        )

    def setUp(self):
        cache.clear()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_cache(self):
        """Проверка работы кэша."""
        response = self.authorized_client.get(reverse("posts:index"))
        r_1 = response.content
        Post.objects.get(id=1).delete()
        response2 = self.authorized_client.get(reverse("posts:index"))
        r_2 = response2.content
        self.assertEqual(r_1, r_2)


class PaginatorViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='user')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='slug',
            description='Тестовое описание',
        )
        cls.number_of_posts = 13
        cls.posts_on_first_page = 10
        cls.posts_on_second_page = 3
        cls.url_pages = [
            reverse('posts:index'),
            reverse('posts:group_list', kwargs={'slug': cls.group.slug}),
            reverse('posts:profile', kwargs={'username': cls.user.username}),
        ]
        cls.post = []
        for _ in range(0, cls.number_of_posts):
            cls.post.append(Post(author=cls.user, group=cls.group))
        Post.objects.bulk_create(cls.post)

    def setUp(self):
        cache.clear()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_paginator_on_pages(self):
        """Проверка пагинации."""
        for reverse_ in self.url_pages:
            with self.subTest(reverse_=reverse_):
                self.assertEqual(len(self.authorized_client.get(
                    reverse_).context.get('page_obj')),
                    self.posts_on_first_page
                )
                self.assertEqual(len(self.authorized_client.get(
                    reverse_ + '?page=2').context.get('page_obj')),
                    self.posts_on_second_page
                )


class FollowViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create(
            username='user',
        )
        cls.post_follower = User.objects.create(
            username='post_follower',
        )
        cls.post = Post.objects.create(
            text='Подпишись на меня',
            author=cls.user,
        )

    def setUp(self):
        cache.clear()
        self.author_client = Client()
        self.author_client.force_login(self.post_follower)
        self.follower_client = Client()
        self.follower_client.force_login(self.user)

    def test_follow_on_user(self):
        """Авторизованный пользователь может подписываться."""
        count_follow = Follow.objects.count()
        self.follower_client.post(
            reverse(
                'posts:profile_follow',
                kwargs={'username': self.post_follower}))
        self.assertEqual(Follow.objects.count(), count_follow + 1)
        self.assertTrue(
            Follow.objects.filter(
                user=self.user,
                author=self.post_follower
            ).exists()
        )

    def test_unfollow_on_user(self):
        """Авторизованный пользователь может отписываться."""
        Follow.objects.create(
            user=self.user,
            author=self.post_follower)
        count_follow = Follow.objects.count()
        self.follower_client.post(
            reverse(
                'posts:profile_unfollow',
                kwargs={'username': self.post_follower}))
        self.assertEqual(Follow.objects.count(), count_follow - 1)
        self.assertFalse(
            Follow.objects.filter(
                user=self.user,
                author=self.post_follower
            ).exists()
        )

    def test_follow_on_authors(self):
        """Новая запись пользователя появляется в ленте подписчиков."""
        Follow.objects.create(
            user=self.post_follower,
            author=self.user)
        response = self.author_client.get(
            reverse('posts:follow_index'))
        self.assertIn(self.post, response.context['page_obj'].object_list)

    def test_notfollow_on_authors(self):
        """Новая запись пользователя не появляется в ленте неподписчиков."""
        response = self.author_client.get(
            reverse('posts:follow_index'))
        self.assertNotIn(self.post, response.context['page_obj'].object_list)


# Видела у некоторых ребят в группе, что они выносили тестирование комментариев
# отдельным классом. Насколько это имеет смысл?
# И как правильнее? У нас в ЯП нет в уроках информации по этому поводу.
class CommentViewTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(
            username='UserAutorized'
        )
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-group',
            description='Тестовое описание группц',
        )
        cls.post = Post.objects.create(
            text='Тестовый пост',
            author=cls.user,
            group=cls.group,
        )
        cls.comment = Comment.objects.create(
            author=cls.user,
            post=cls.post,
            text='Тестовый комментарий',
        )

    def setUp(self):
        cache.clear()
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_comments_by_authorized_user(self):
        """Проверка возможности комментировать посты
        авторизованной учеткой."""
        comment_count = Comment.objects.count()
        form_data = {
            'author': self.user,
            'post': self.post,
            'text': 'Тестовый комментарий',
        }
        response = self.authorized_client.post(
            reverse('posts:add_comment', kwargs={'post_id': self.post.id}),
            data=form_data,
            follow=True
        )
        self.assertEqual(Comment.objects.count(), comment_count + 1)
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_comments_checking_add_by_guest_user(self):
        """Проверка возможности комментировать посты
         неавторизованной учеткой."""
        comment_count = Comment.objects.count()
        form_data = {
            'author': self.user,
            'post': self.post,
            'text': 'Тестовый комментарий',
        }
        response = self.guest_client.post(
            reverse('posts:add_comment', kwargs={'post_id': self.post.id}),
            data=form_data,
            follow=True
        )
        self.assertEqual(Comment.objects.count(), comment_count)
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_comments_checking_render_on_page(self):
        """Проверка успешной отправки комментария на страницу."""
        response_authorized = self.authorized_client.get(
            reverse('posts:post_detail', kwargs={'post_id': self.post.id})
        )
        response_guest = self.guest_client.get(
            reverse('posts:post_detail', kwargs={'post_id': self.post.id})
        )
        self.assertEqual(
            response_authorized.context['comments'][0],
            self.comment
        )
        self.assertEqual(
            response_guest.context['comments'][0],
            self.comment
        )
