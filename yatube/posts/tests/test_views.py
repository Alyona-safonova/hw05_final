from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django import forms
from django.core.cache import cache

from ..models import Post, Group, Comment, Follow

User = get_user_model()


class PostPagesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.user1 = User.objects.create_user(username='leo')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание'
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

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        self.author = Client()
        self.author.force_login(self.user1)

    def test_pages_uses_correct_template(self):
        """проверяем, что во view-функциях используются
        правильные html-шаблоны."""
        templates_pages_names = {
            reverse("posts:index"): "posts/index.html",
            reverse(
                "posts:group_posts", kwargs={"slug": self.group.slug}
            ): "posts/group_list.html",
            reverse(
                "posts:profile", kwargs={"username": self.post.author}
            ): "posts/profile.html",
            reverse(
                "posts:post_detail", kwargs={"post_id": self.post.id}
            ): "posts/post_detail.html",
            reverse(
                "posts:post_edit", kwargs={"post_id": self.post.id}
            ): "posts/create_post.html",
            reverse("posts:post_create"): "posts/create_post.html",
        }

        for reverse_name, template in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_index_show_correct_context(self):
        """Шаблон index сформирован с правильным контекстом."""
        response = self.guest_client.get(reverse("posts:index"))
        self.check_card_of_post(response.context["page_obj"][0])

    def test_group_list_show_correct_context(self):
        """Шаблон group_list сформирован с правильным контекстом."""
        response = self.guest_client.get(
            reverse("posts:group_posts", kwargs={"slug": self.group.slug})
        )
        self.check_card_of_post(response.context["page_obj"][0])
        self.assertIn('group', response.context)

    def test_profile_show_correct_context(self):
        """Шаблон profile сформирован с правильным контекстом."""
        response = self.guest_client.get(
            reverse("posts:profile", args=(self.post.author,))
        )
        self.assertIn('author', response.context)
        self.check_card_of_post(response.context["page_obj"][0])

    def test_post_detail_show_correct_context(self):
        """Шаблон post_detail сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse("posts:post_detail", kwargs={"post_id": self.post.id})
        )
        self.assertIn('post', response.context)
        self.check_card_of_post(response.context.get("post"))

    def test_edit_show_correct_context(self):
        """Шаблон edit сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse("posts:post_edit", kwargs={"post_id": self.post.id})
        )
        self.assertIn('form', response.context)
        self.assertTrue(response.context.get("is_edit"))
        form_fields = {
            "text": forms.fields.CharField,
            "group": forms.fields.ChoiceField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get("form").fields.get(value)
                self.assertIsInstance(form_field, expected)

    def test_create_show_correct_context(self):
        """Шаблон create сформирован с правильным контекстом."""
        response = self.authorized_client.get(reverse("posts:post_create"))
        form_fields = {
            "text": forms.fields.CharField,
            "group": forms.fields.ChoiceField,
            "image": forms.fields.ImageField,
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get("form").fields.get(value)
                self.assertIsInstance(form_field, expected)

    def test_create_post_in_pages(self):
        """Дополнительная проверка при создании поста."""
        pages = (
            reverse("posts:index"),
            reverse("posts:group_posts", kwargs={'slug': 'test-slug'}),
            reverse("posts:profile", kwargs={'username': 'auth'})
        )
        for page in pages:
            response = self.authorized_client.get(page)
            post = response.context['page_obj'][0]
            self.check_card_of_post(post)

    def check_card_of_post(self, post):
        self.assertEqual(post.text, self.post.text)
        self.assertEqual(post.author.username, self.user.username)
        self.assertEqual(post.group.id, self.group.id)
        self.assertEqual(post.image, self.post.image)

    def test_comment_correct_context(self):
        """Валидная форма Комментария создает запись в Post."""
        comments_count = Comment.objects.count()
        form_data = {"text": "Тестовый коммент"}
        response = self.authorized_client.post(
            reverse("posts:add_comment", kwargs={"post_id": self.post.id}),
            data=form_data,
            follow=True,
        )
        self.assertRedirects(
            response, reverse(
                "posts:post_detail", kwargs={"post_id": self.post.id}
            )
        )
        self.assertEqual(Comment.objects.count(), comments_count + 1)
        self.assertTrue(Comment.objects.filter(
            text="Тестовый коммент"
        ).exists())

    def test_cache_index(self):
        """Тестирование кэша."""
        response = self.guest_client.get(reverse("posts:index"))
        response_1 = response.content
        Post.objects.get(id=self.post.id).delete()
        response2 = self.guest_client.get(reverse("posts:index"))
        response_2 = response2.content
        self.assertEqual(response_1, response_2)
        cache.clear()
        response3 = self.guest_client.get(reverse('posts:index'))
        response_3 = response3.content
        self.assertNotEqual(response_2, response_3)

    def test_follow_page(self):
        """Авторизованный пользователь может подписываться
        на других пользователей и отписываться."""
        Follow.objects.get_or_create(user=self.user, author=self.post.author)
        response_2 = self.authorized_client.get(reverse("posts:follow_index"))
        self.assertEqual(len(response_2.context["page_obj"]), 1)
        self.assertIn(self.post, response_2.context["page_obj"])
        Follow.objects.all().delete()
        response_3 = self.authorized_client.get(reverse("posts:follow_index"))
        self.assertEqual(len(response_3.context["page_obj"]), 0)

    def test_follow_page_user_follower(self):
        """Проверяем что пост не появился
        в избранных у пользователя подписчика."""
        outsider = User.objects.create(username="NoName")
        self.authorized_client.force_login(outsider)
        response_2 = self.authorized_client.get(reverse("posts:follow_index"))
        self.assertNotIn(self.post, response_2.context["page_obj"])

    def test_follow_correct(self):
        Follow.objects.create(user=self.user, author=self.post.author)
        response = self.authorized_client.get(
            reverse('posts:follow_index')
        )
        post_text = response.context['page_obj'][0].text
        self.assertEqual(post_text, 'Тестовый пост')
        response = self.author.get(
            reverse('posts:follow_index')
        )
        self.assertFalse(response.context['page_obj'])

    def test_follow(self):
        """Тестирование подписки."""
        follow_count = Follow.objects.count()
        self.author.post(
            reverse(
                'posts:profile_follow',
                kwargs={'username': self.user.username}
            )
        )
        follow = Follow.objects.last()
        self.assertEqual(Follow.objects.count(), follow_count + 1)
        self.assertEqual(follow.author, self.user)
        self.assertEqual(follow.user, self.user1)

    def test_unfollow(self):
        """Тестирование отписки."""
        Follow.objects.create(
            user=self.user1,
            author=self.user)
        follow_count = Follow.objects.count()
        self.author.post(
            reverse(
                'posts:profile_unfollow',
                kwargs={'username': self.user.username}
            )
        )
        self.assertEqual(Follow.objects.count(), follow_count - 1)

class PaginatorViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание'
        )
        posts = [
            Post(
                author=cls.user,
                text='Тестовый пост {i}',
                group=cls.group
            )
            for i in range(1, 15)
        ]
        Post.objects.bulk_create(objs=posts)

    def setUp(self):
        self.guest_client = Client()
        self.author = Client()
        self.author.force_login(self.user)

    def test_first_page_contains_ten_records(self):
        """Паджинатор тест страницы 1."""
        response = self.author.get(reverse('posts:index'))
        self.assertEqual(len(response.context['page_obj']), 10)

    def test_second_page_contains_three_records(self):
        """Паджинатор тест страницы 2."""
        response = self.author.get(reverse('posts:index') + '?page=2')
        self.assertEqual(len(response.context['page_obj']), 4)
