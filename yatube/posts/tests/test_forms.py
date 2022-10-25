import shutil
import tempfile
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import Post, Group, User

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostFormTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание'
        )
        cls.group1 = Group.objects.create(
            title='Изменяем текст',
            slug='test-slug1',
            description='Тестовое описание1'
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост',
            group=cls.group
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_create_post(self):
        """Валидная форма создает запись в Post."""
        posts_count = Post.objects.count()
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
        form_data = {
            'text': 'Тестовый текст',
            'group': self.group.id,
            'image': uploaded
        }
        response = self.authorized_client.post(
            reverse("posts:post_create"), data=form_data, follow=True
        )
        self.assertRedirects(
            response, reverse("posts:profile", kwargs={"username": self.user})
        )
        self.assertEqual(Post.objects.count(), posts_count + 1)
        self.assertEqual(Post.objects.first().text, form_data['text'])
        self.assertEqual(Post.objects.first().group, self.group)
        self.assertEqual(Post.objects.first().image, 'posts/small.gif')

    def test_post_edit(self):
        """Валидная форма изменяет запись в Post."""
        posts_count = Post.objects.count()
        form_data = {
            "text": "Изменяем текст",
            "group": self.group1.id
        }
        response = self.authorized_client.post(
            reverse("posts:post_edit", kwargs=({"post_id": self.post.id})),
            data=form_data,
            follow=True,
        )
        self.assertRedirects(
            response, reverse(
                "posts:post_detail", kwargs={"post_id": self.post.id}
            )
        )
        self.assertEqual(Post.objects.count(), posts_count)
        self.assertEqual(Post.objects.get(
            id=self.post.id).text, form_data['text']
        )
        self.assertEqual(
            Post.objects.get(id=self.post.id).group.id, form_data['group']
        )

    def test_guest_cannot_edit_post(self):
        """Валидная форма не изменит запись в Post если неавторизован."""
        posts_count = Post.objects.count()
        form_data = {
            "text": "Тестовый пост",
            "group": self.group.id
        }
        response = self.guest_client.post(
            reverse("posts:post_edit", kwargs=({"post_id": self.post.id})),
            data=form_data,
            follow=True,
        )
        self.assertRedirects(
            response, f"/auth/login/?next=/posts/{self.post.id}/edit/"
        )
        self.assertEqual(Post.objects.count(), posts_count)

    def test_guest_cannot_create(self):
        """Валидная форма не создаст запись в Post если неавторизован."""
        posts_count = Post.objects.count()
        form_data = {
            "text": "Тестовый пост",
            "group": self.group.id
        }
        response = self.guest_client.post(
            reverse("posts:post_create"),
            data=form_data,
            follow=True,
        )
        self.assertRedirects(
            response, "/auth/login/?next=/create/"
        )
        self.assertEqual(Post.objects.count(), posts_count)
