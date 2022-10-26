from django.test import TestCase, Client

from ..models import Post, Group, User


class PostURLTests(TestCase):
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
        cls.post = Post.objects.create(
            author=cls.user1,
            text='Тестовый пост'
        )
        cls.url_names = [
            "/",
            f"/group/{cls.group.slug}/",
            f"/profile/{cls.user}/",
            f"/posts/{cls.post.id}/",
        ]
        cls.templates_url_names = {
            "/": "posts/index.html",
            f"/group/{cls.group.slug}/": "posts/group_list.html",
            f"/profile/{cls.user.username}/": "posts/profile.html",
            f"/posts/{cls.post.id}/": "posts/post_detail.html",
            f"/posts/{cls.post.id}/edit/": "posts/create_post.html",
            "/create/": "posts/create_post.html",
        }

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        self.author = Client()
        self.author.force_login(self.user1)

    def test_exists_at_desired_location(self):
        """Тестируем страницы доступные всем."""
        for address in self.url_names:
            with self.subTest(address):
                response = self.authorized_client.get(address)
                self.assertEqual(response.status_code, 200)

    def test_urls_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        for url, template in self.templates_url_names.items():
            with self.subTest(template=template):
                response = self.author.get(url)
                self.assertTemplateUsed(response, template)

    def test_post_unexisting_page(self):
        """Страница /unexisting_page/ должна выдать ошибку."""
        response = self.guest_client.get('/unexisting_page/')
        self.assertEqual(response.status_code, 404)

    def test_list_url_redirect_guest(self):
        """Проверяем редиректы для неавторизованного пользователя."""
        url_names_redirects = {
            f'/posts/{self.post.id}/edit/':
                f'/auth/login/?next=/posts/{self.post.id}/edit/',
            '/create/': '/auth/login/?next=/create/',
        }
        for address, redirect_address in url_names_redirects.items():
            with self.subTest(address=address):
                response = self.guest_client.get(address, follow=True)
                self.assertRedirects(response, redirect_address)

    def test_post_create_for_authorized_client(self):
        """Проверяем, что авторизованному пользователю
        доступно создание поста."""
        response = self.authorized_client.get('/create/')
        self.assertEqual(response.status_code, 200)

    def test_post_edit_for_author(self):
        """Проверяем, что автору доступно редактирование поста."""
        response = self.author.get(f'/posts/{self.post.id}/edit/')
        self.assertEqual(response.status_code, 200)

    def test_edit_for_authorized_client(self):
        """проверяем, что не автор поста не может редактировать пост."""
        response = self.authorized_client.get(
            f'/posts/{self.post.id}/edit/', follow=True
        )
        self.assertRedirects(response, f'/posts/{self.post.id}/')
