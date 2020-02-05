import json
from functools import wraps
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from ratelimit.decorators import ratelimit
from ratelimit.utils import get_usage_count

def simple_ratelimit(handler, rate):
    'A handler that silently drops requests over the rate limit.'
    @require_POST
    @ratelimit(key='user_or_ip', rate=rate, block=True)
    @wraps(handler)
    def rate_limiter(request):
        return HttpResponse(handler(request))
    return rate_limiter

# Usage: mypuzzle_submit = simple_ratelimit(mypuzzle.submit, '10/s')

def check_ratelimit(request, rate):
    data = get_usage_count(request, group=request.path, rate=rate, key='user_or_ip')
    return data['count'] >= data['limit']

def update_ratelimit(request, rate):
    get_usage_count(request, group=request.path, rate=rate, key='user_or_ip', increment=True)

def error_ratelimit(handler, rate, error, check_response=None, encode_response=None):
    '''
    A handler that checks and reports errors to the client.

    error should be a message, in the same format (HTML, JSON, etc.) as the
    data that handler would return, that can be interpreted in the browser to
    tell the user what's going on.

    This decorator is designed so that if the user is not currently blocked,
    you can run the handler and use its output to decide whether to increment
    the rate limit counter or not. For example, you might only count incorrect
    guesses towards the limit. If you don't care about this, don't pass
    check_response.

    encode_response is run on either error or the handler output. This lets you
    for example use Python dicts for error, handler, and check_response, while
    still serializing to JSON in the end.
    '''
    @require_POST
    @wraps(handler)
    def rate_limiter(request):
        if check_ratelimit(request, rate):
            response = error
            update_ratelimit(request, rate)
        else:
            if check_response is None:
                update_ratelimit(request, rate)
            response = handler(request)
            if check_response is not None and not check_response(response):
                update_ratelimit(request, rate)
        if encode_response is not None:
            response = encode_response(response)
        return HttpResponse(response)
    return rate_limiter

# Usage: mypuzzle_submit = error_ratelimit(mypuzzle.submit, '2/m', {'error': 'Please limit your attempts to twice a minute.'}, lambda response: response['was_correct'], json.dumps)
