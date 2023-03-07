# в тесты ЯП встроена проверка, что статус должен быть указан именно
# в таком виде, как сейчас. Этот фрагмент мы копировали из уроков.
# Я понимаю, как реализовать вашу рекомендацию: импортировать HTTPStatus
# и вместо status=404 написать HTTPStatus.NOT_FOUND,
# но тогда у меня pytest не проходит.
from django.shortcuts import render


def page_not_found(request, exception):
    return render(request, 'core/404.html', {'path': request.path}, status=404)


def csrf_failure(request, reason=''):
    return render(request, 'core/403csrf.html')
