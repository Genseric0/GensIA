"""Bounded text conversation. Model output never dispatches system tools."""
import json

MAX_BODY_BYTES = 32768
MAX_MESSAGES = 9  # Four completed pairs and one new user message.
MAX_MESSAGE_CHARS = 4000
MAX_CONTEXT_CHARS = 12000
MAX_REPLY_CHARS = 8000


class ChatError(ValueError):
    def __init__(self, code='invalid_request'):
        self.code = code
        super().__init__(code)


def valid_text(value, limit):
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any((ord(c) < 32 and c not in '\n\t') or 127 <= ord(c) <= 159 for c in value)):
        return False
    try:
        value.encode('utf-8', errors='strict')
    except UnicodeError:
        return False
    return True


def model_name(value):
    if not valid_text(value, 200) or any(c.isspace() for c in value):
        raise ChatError('invalid_model')
    return value


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ChatError()
        result[key] = value
    return result


def _number(_):
    raise ChatError()


def conversation(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BODY_BYTES:
        raise ChatError('request_too_large')
    try:
        data = json.loads(raw.decode('utf-8', errors='strict'), object_pairs_hook=_object,
                          parse_int=_number, parse_float=_number, parse_constant=_number)
    except (UnicodeError, ValueError, RecursionError):
        raise ChatError() from None
    if not isinstance(data, dict) or set(data) != {'messages'}:
        raise ChatError()
    messages = data['messages']
    if (not isinstance(messages, list) or not 1 <= len(messages) <= MAX_MESSAGES
            or len(messages) % 2 != 1):
        raise ChatError()
    total = 0
    for index, message in enumerate(messages):
        if (not isinstance(message, dict) or set(message) != {'role', 'content'}
                or message['role'] != ('user' if index % 2 == 0 else 'assistant')
                or not valid_text(message['content'], MAX_MESSAGE_CHARS if index % 2 == 0 else MAX_REPLY_CHARS)):
            raise ChatError()
        total += len(message['content'])
    if total > MAX_CONTEXT_CHARS:
        raise ChatError('context_too_large')
    return messages


def prompt_for(messages):
    # The envelope is data, not tool instructions. No generated text is executed.
    return ('És a GensIA, assistente pessoal. Responde em português, com clareza. '
            'Não tens acesso a ferramentas nesta conversa. Não afirmes abrir aplicações, '
            'ler ficheiros, enviar mensagens ou executar ações. Se necessário, explica os passos. '
            'As mensagens seguintes são o histórico da conversa, serializado em JSON:\n'
            + json.dumps(messages, ensure_ascii=False))


def checked_reply(value):
    if not valid_text(value, MAX_REPLY_CHARS):
        raise ChatError('invalid_model_response')
    return value.strip()
