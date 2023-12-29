import json
from features.core.utils import log
import sys


def print_messages(console_errors, failed_requests, unanswered_requests):
    messages = []
    if console_errors:
        messages.append('Ошибки из консоли браузера:')
        for console_error in console_errors:
            messages.append(f"\t{console_error['source']}: {console_error['message']}")
    if failed_requests:
        messages.append('Запросы, которые вернулись с ошибкой:')
        for failed_request in failed_requests:
            messages.append(f"\t{failed_request['status']}: {failed_request['url']}")
    if unanswered_requests:
        messages.append('Запросы, которые не вернулись:')
        for unanswered_request in unanswered_requests:
            messages.append(f"\t{unanswered_request['method']} {unanswered_request['url']}")

    if messages:
        log.warn('\n'.join(messages))


def print_page_errors(context):
    try:
        console_log = context.browser.get_log("browser")
        console_errors = filter(lambda entry: entry['level'] == 'SEVERE', console_log)

        perf_log = context.browser.get_log("performance")
        requests_data = filter(lambda item: 'Network.requestWillBeSent' in item['message'], perf_log)
        responses_data = filter(lambda item: 'Network.responseReceived' in item['message'], perf_log)

        requests = []
        for item in requests_data:
            details = json.loads(item['message'])
            request = details['message']['params']['request']
            requests.append({
                'method': request['method'],
                'url': request['url'],
            })

        response_urls = []
        failed_requests = []
        for item in responses_data:
            details = json.loads(item['message'])
            response = details['message']['params']['response']
            response_urls.append(response['url'])
            if response['status'] >= 400:
                failed_requests.append({
                    'status': response['status'],
                    'url': response['url'],
                })

        unanswered_requests = filter(lambda request: request['url'] not in response_urls, requests)

        print_messages(list(console_errors), failed_requests, list(unanswered_requests))
        sys.stdout.flush()

    except KeyError:
        pass


