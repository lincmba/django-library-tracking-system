import datetime
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from .models import Author, Book, Member, Loan
from .serializers import AuthorSerializer, BookSerializer, MemberSerializer, LoanSerializer
from rest_framework.decorators import action
from django.utils import timezone
from .tasks import send_loan_notification
from django.db.models import Count, Q

class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    pagination_class = PageNumberPagination

    @action(detail=True, methods=['post'])
    def loan(self, request, pk=None):
        book = self.get_object()
        if book.available_copies < 1:
            return Response({'error': 'No available copies.'}, status=status.HTTP_400_BAD_REQUEST)
        member_id = request.data.get('member_id')
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            return Response({'error': 'Member does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan = Loan.objects.create(book=book, member=member)
        book.available_copies -= 1
        book.save()
        send_loan_notification.delay(loan.id)
        return Response({'status': 'Book loaned successfully.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def return_book(self, request, pk=None):
        book = self.get_object()
        member_id = request.data.get('member_id')
        try:
            loan = Loan.objects.get(book=book, member__id=member_id, is_returned=False)
        except Loan.DoesNotExist:
            return Response({'error': 'Active loan does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan.is_returned = True
        loan.return_date = timezone.now().date()
        loan.save()
        book.available_copies += 1
        book.save()
        return Response({'status': 'Book returned successfully.'}, status=status.HTTP_200_OK)

class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer

    @action(detail=False, methods=['get'])
    def top_active(self, request):
        queryset = (
            Member.objects
            .select_related('user')
            .annotate(
                active_loans=Count('loans', filter=Q(loans__is_returned=False))
            )
            .filter(active_loans__gt=0)
            .order_by('-active_loans')[:5]
        )
        data = [
            {
                "id": member.id,
                "username": member.user.username,
                "email": member.user.email,
                "active_loans": member.active_loans,
            }
            for member in queryset
        ]
        return Response(data)

class LoanViewSet(viewsets.ModelViewSet):
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer

    @action(detail=True, methods=['post'])
    def extend_due_date(self, request, pk=None):
        loan = self.get_object()
        today = timezone.now().date
        days = int(request.data.get("additional_days"))

        if loan.is_returned:
            return Response({"error": "Cannot extend date pf returned loan"}, status=status.HTTP_400_BAD_REQUEST)
        if not loan.due_date or loan.due_date < today:
            return Response({"Error": "Past return date"}, status=status.HTTP_400_BAD_REQUEST)
        if days < 1:
            return Response({"Error": "Days must be postive integer"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            loan.due_date += datetime.timedelta(days=days)
            return Response(self.serializer_class(loan).data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"Error": f"An error occured {e}"})
