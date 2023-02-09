from django.utils import timezone


def year(request):
    now = timezone.now()
    context = {'year': now.year}
    return context
