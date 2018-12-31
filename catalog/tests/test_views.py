from django.test import TestCase
from django.urls import reverse

from catalog.models import Author

class AuthorListViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        #create 13 authors for pagination tests
        number_of_authors = 13

        for author_id in range(number_of_authors):
            Author.objects.create(
                first_name=f'Christian {author_id}',
                last_name=f'Surname {author_id}',
                )

    def test_view_url_exists_at_desired_location(self):
        response = self.client.get('/catalog/authors/')
        self.assertEqual(response.status_code, 200)

    def test_view_url_accessible_by_name(self):
        response = self.client.get(reverse('authors'))
        self.assertEqual(response.status_code,200)

    def test_view_uses_correct_template(self):
        response = self.client.get(reverse('authors'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'catalog/author_list.html')

    def test_pagination_is_ten(self):
        response = self.client.get(reverse('authors'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue('is_paginated' in response.context)
        self.assertTrue(response.context['is_paginated'] == True)
        self.assertTrue(len(response.context['author_list']) == 10)

    def test_lists_all_authors(self):
        #get second page and confirm it has (exactly) remaining 3 items
        response = self.client.get(reverse('authors')+'?page=2')
        self.assertEqual(response.status_code, 200)
        self.assertTrue('is_paginated' in response.context)
        self.assertTrue(response.context['is_paginated'] == True)
        self.assertTrue(len(response.context['author_list']) == 3)

import datetime

from django.utils import timezone
from django.contrib.auth.models import User #required to assign User as a borrower

from catalog.models import BookInstance, Book, Genre, Language

class LoanedBookInstancesByUserListViewTest(TestCase):
    def setUp(self):
        #create two users
        test_user1 = User.objects.create_user(username = 'testuser1', password='1X<ISRUkw+tuK')
        test_user2 = User.objects.create_user(username='testuser2', password='2HJ1vRV0Z&3iD')

        test_user1.save()
        test_user2.save()

        #create a book
        test_author = Author.objects.create(first_name='John', last_name='Smith')
        test_genre = Genre.objects.create(name='Fantasy')
        test_language = Language.objects.create(name='English')
        test_book = Book.objects.create(
            title = 'Book Title',
            summary = 'My book summary',
            isbn = 'ABCDEFG',
            author=test_author,
            language = test_language,
        )

        #create genre as a post-step
        genre_objects_for_book = Genre.objects.all()
        test_book.genre.set(genre_objects_for_book) #direct assignement of many-to-many types not allowed
        test_book.save()

        #create 30 BookInstance objects
        number_of_book_copies = 30
        for book_copy in range(number_of_book_copies):
            return_date = timezone.now() + datetime.timedelta(days=book_copy%5)
            the_borrower = test_user1 if book_copy % 2 else test_user2
            status = 'm'
            BookInstance.objects.create(
                book=test_book,
                imprint = 'Unlikely Imprint, 2016',
                due_back = return_date,
                borrower = the_borrower,
                status=status,
            )

    def test_redirect_if_not_logged_in(self):
        response = self.client.get(reverse('my-borrowed'))
        self.assertRedirects(response, '/accounts/login/?next=/catalog/mybooks/')

    def test_logged_in_uses_correct_template(self):
        login = self.client.login(username='testuser1', password='1X<ISRUkw+tuK')
        response = self.client.get(reverse('my-borrowed'))

        #check our user is logged in
        self.assertEqual(str(response.context['user']), 'testuser1')
        #check that we go a response "success"
        self.assertEqual(response.status_code, 200)

        #check we used correct template
        self.assertTemplateUsed(response, 'catalog/bookinstance_list_borrowed_user.html')

    def test_only_borrowed_books_in_list(self):
        login = self.client.login(username='testuser1', password='1X<ISRUkw+tuK')
        response = self.client.get(reverse('my-borrowed'))

        #check our user is logged in
        self.assertEqual(str(response.context['user']), 'testuser1')
        #check that we got a response "success"
        self.assertEqual(response.status_code, 200)

        #check that initially we don't have any books in list (none on loan)
        self.assertTrue('bookinstance_list' in response.context)
        self.assertEqual(len(response.context['bookinstance_list']), 0)

        #now change all books to be on loan
        books = BookInstance.objects.all()[:10]

        for book in books:
            book.status = 'o'
            book.save()

        #check that now we ahve borrowed books in the list
        response = self.client.get(reverse('my-borrowed'))
        #check user is logged in
        self.assertEqual(str(response.context['user']), 'testuser1')
        #check that response is 200
        self.assertEqual(response.status_code, 200)

        self.assertTrue('bookinstance_list' in response.context)

        #confirm all books belong to testuser1 and are on loan
        for bookitem in response.context['bookinstance_list']:
            self.assertEqual(response.context['user'], bookitem.borrower)
            self.assertEqual('o', bookitem.status)

    def test_pages_ordered_by_due_date(self):
        #change all books to be on loan
        for book in BookInstance.objects.all():
            book.status='o'
            book.save()

        login = self.client.login(username='testuser1', password = '1X<ISRUkw+tuK')
        response = self.client.get(reverse('my-borrowed'))

        #check user is logged in
        self.assertEqual(str(response.context['user']), 'testuser1')
        #check that response is 200
        self.assertEqual(response.status_code, 200)

        #confirm that 10 items displayed due to pagination
        self.assertEqual(len(response.context['bookinstance_list']), 10)

        last_date = 0
        for book in response.context['bookinstance_list']:
            if last_date == 0:
                last_date = book.due_back
            else:
                self.assertTrue(last_date <= book.due_back)
                last_date = book.due_back

import uuid
#required to grant permission needed to set a book as returned
from django.contrib.auth.models import Permission

class RenewBookInstancesViewTest(TestCase):
    def setUp(self):
        #create a user
        test_user1 = User.objects.create_user(username='testuser1', password = '1X<ISRUkw+tuK')
        test_user2 = User.objects.create_user(username='testuser2', password = '1X<ISRUkw+tuK')

        test_user1.save()
        test_user2.save()

        permission = Permission.objects.get(name='Set book as returned')
        test_user2.user_permissions.add(permission)
        test_user2.save()

        #create a book
        test_author = Author.objects.create(first_name='John', last_name='Smith')
        test_genre = Genre.objects.create(name='Fantasy')
        test_language = Language.objects.create(name='English')
        test_book = Book.objects.create(
            title = 'Book Title',
            summary = 'My book summary',
            isbn = 'abcd',
            author = test_author,
            language = test_language,
        )

        #create genre as past-step
        genre_objects_for_book = Genre.objects.all()
        test_book.genre.set(genre_objects_for_book) #direct assignement of many-to-many not allowed
        test_book.save()

        #create a bookinstance object for test_user1
        return_date = datetime.date.today() + datetime.timedelta(days=5)
        self.test_bookinstance1 = BookInstance.objects.create(
            book = test_book,
            imprint = 'Unlikely Imprint, 2016',
            due_back = return_date,
            borrower = test_user1,
            status='o',
        )

        #create a bookinstance for test_user2
        return_date = datetime.date.today() + datetime.timedelta(days=5)
        self.test_bookinstance2 = BookInstance.objects.create(
            book=test_book,
            imprint='Unlikely Imprint, 2016',
            due_back=return_date,
            borrower=test_user2,
            status='o',
        )

    def test_redirect_if_not_logged_in(self):
        response = self.client.get(reverse('renew-book-librarian',
        kwargs = {'pk':self.test_bookinstance1.pk}))
        #manually check redirect (can't user assertRedirect, since url is dynamic)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login'))

    def test_redirect_if_logged_in_but_not_correct_permisison(self):
        login = self.client.login(username='testuser1', password='1X<ISRUkw+tuK')
        response = self.client.get(reverse('renew-book-librarian',
        kwargs = {'pk': self.test_bookinstance1.pk}))
        self.assertEqual(response.status_code, 302)

    def test_logged_in_with_permission_borrowed_book(self):
        login = self.client.login(username='testuser2', password='1X<ISRUkw+tuK')
        response = self.client.get(reverse('renew-book-librarian',
        kwargs = {'pk': self.test_bookinstance2.pk}))
        #check if logged in with our book and correct permissions
        self.assertEqual(response.status_code, 200)

    def test_logged_in_with_permission_another_users_borrowed_book(self):
        login = self.client.login(username='testuser2', password = '1X<ISRUkw+tuK')
        response = self.client.get(reverse('renew-book-librarian', kwargs = {'pk':self.test_bookinstance1.pk}))

        #check that it lets us login. We're a lirbarian so we can view other users' books
        self.assertEqual(response.status_code, 200)

    def test_HTTP404_for_invalid_book_if_logged_in(self):
        test_uid = uuid.uuid4()
        login = self.client.login(username='testuser2', password = '1X<ISRUkw+tuK')
        response = self.client.get(reverse('renew-book-librarian', kwargs = {'pk':test_uid}))
        self.assertEqual(response.status_code, 404)

    def test_uses_correct_template(self):
        login = self.client.login(username='testuser2', password = '1X<ISRUkw+tuK')
        response = self.client.get(reverse('renew-book-librarian', kwargs = {'pk':self.test_bookinstance1.pk}))
        self.assertEqual(response.status_code, 200)
        #check correct template
        self.assertTemplateUsed(response, 'catalog/book_renew_librarian.html')

    def test_form_renewal_date_initially_has_date_three_weeks_in_future(self):
        login = self.client.login(username='testuser2', password = '1X<ISRUkw+tuK')
        response = self.client.get(reverse('renew-book-librarian', kwargs = {'pk':self.test_bookinstance1.pk}))
        self.assertEqual(response.status_code, 200)

        date_3_weeks_in_future = datetime.date.today() + datetime.timedelta(weeks=3)
        self.assertEqual(response.context['form'].initial['renewal_date'], date_3_weeks_in_future)

    def test_redirects_to_all_borrowed_book_list_on_success(self):
        login = self.client.login(username='testuser2', password = '1X<ISRUkw+tuK')
        valid_date_in_future = datetime.date.today() + datetime.timedelta(weeks=2)
        response = self.client.post(reverse('renew-book-librarian',
        kwargs={'pk':self.test_bookinstance1.pk,}), {'renewal_date':valid_date_in_future})
        self.assertRedirects(response, reverse('all-borrowed'))

    def test_form_invalid_renewal_date_past(self):
        login = self.client.login(username='testuser2', password = '1X<ISRUkw+tuK')
        date_in_past = datetime.date.today() - datetime.timedelta(weeks=1)
        response = self.client.post(reverse('renew-book-librarian',
        kwargs = {'pk': self.test_bookinstance1.pk}), {'renewal_date': date_in_past})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'renewal_date', 'Invalid date - renewal in past')

    def test_form_invalid_renewal_date_future(self):
        login = self.client.login(username='testuser2', password = '1X<ISRUkw+tuK')
        invalid_date_in_future = datetime.date.today() + datetime.timedelta(weeks=5)
        response = self.client.post(reverse('renew-book-librarian',
        kwargs = {'pk': self.test_bookinstance1.pk}), {'renewal_date': invalid_date_in_future})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'renewal_date', 'Invalid date - renewal more than 4 weeks ahead')


class AuthorCreateTest(TestCase):
    def setUp(self):
        #create users
        test_user1 = User.objects.create_user(username='testuser1', password = '1X<ISRUkw+tuK')
        test_user2 = User.objects.create_user(username='testuser2', password = '1X<ISRUkw+tuK')

        test_user1.save()
        test_user2.save()

        permission = Permission.objects.get(name='Set book as returned')
        test_user2.user_permissions.add(permission)
        test_user2.save()

        self.test_author = Author.objects.create(
            first_name = 'Christopher',
            last_name = 'Hitchens',
            date_of_birth = '1950-02-04'
        )

        self.first_name = 'Michael'
        self.last_name = 'Walters'
        self.date_of_birth = '1950-02-04'

    def test_initial_value_author(self):
        login = self.client.login(username='testuser2', password = '1X<ISRUkw+tuK')
        response = self.client.get(reverse('author_create'))
        self.assertEqual(response.status_code, 200)

        default_death_date = '12/10/2016'
        self.assertEqual(response.context['form'].initial['date_of_death'], default_death_date)


    def test_logged_in_but_incorrect_permission(self):
        login = self.client.login(username='testuser1', password = '1X<ISRUkw+tuK')
        response = self.client.get(reverse('author_create'))
        self.assertEqual(response.status_code, 403)

    def test_redirect_after_author_creation(self):
        #example redirect: http://127.0.0.1:8000/catalog/author/5
        login = self.client.login(username='testuser2', password = '1X<ISRUkw+tuK')
        response = self.client.post(reverse('author_create'),{
            'first_name':self.first_name,
            'last_name':self.last_name,
            'date_of_birth':self.date_of_birth,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/catalog/author'))



    def test_correct_template_author_creation(self):
        login = self.client.login(username='testuser2', password = '1X<ISRUkw+tuK')
        response = self.client.get(reverse('author_create'))
        self.assertTemplateUsed(response, 'catalog/author_form.html')        
