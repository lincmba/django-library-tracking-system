from django.core.management import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask

class Command(BaseCommand):
    def handle(self, *args, **options):
        # create schedule
        name = "Send Overdue Emails"
        cron_schedule, created = CrontabSchedule.objects.get_or_create(
            hour="8", minute="0", day_of_week="*", day_of_month="*", month_of_year="*")
        #delete existing tasks
        PeriodicTask.objects.filter(name=name).delete()
        PeriodicTask.objects.create(
            name=name,
            crontab=cron_schedule,
            task="library.tasks.check_overdue_loans",
            enabled=True
        )
