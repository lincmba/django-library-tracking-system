import datetime
from celery import shared_task
from .models import Loan
from django.core.mail import send_mail
from django.conf import settings

@shared_task
def send_loan_notification(loan_id):
    try:
        loan = Loan.objects.get(id=loan_id)
        member_email = loan.member.user.email
        book_title = loan.book.title
        send_mail(
            subject='Book Loaned Successfully',
            message=f'Hello {loan.member.user.username},\n\nYou have successfully loaned "{book_title}".\nPlease return it by the due date.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member_email],
            fail_silently=False,
        )
    except Loan.DoesNotExist:
        pass

@shared_task
def check_overdue_loans():
    overdue_loans = Loan.objects.filter(
        is_returned=False, 
        due_date__lte=datetime.datetime.now().date).select_related(
            "book", "member__user")
    for loan in overdue_loans:
        try:
            days_overdue = (datetime.datetime.now().date - loan.due_date).days
            member_email = loan.member.user.email
            member_username = loan.member.user.username
            book_title = loan.book.title
            send_mail(
                subject=f"Overdue Book {book_title}",
                message=f"Hello {member_username}. The book {book_title} is overdue by {days_overdue} days. Kindly return it.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[member_email],
                fail_silently=False
            )
        except Exception as e:
            print(f"Error sending overdue notification {e}")
        
