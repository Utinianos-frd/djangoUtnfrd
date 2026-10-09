def error(status_code, detail):
    return {"errors": [{"status": str(status_code), "detail": detail}]}, status_code


def extract_attributes(request):
    try:
        return request.data['data']['attributes']
    except (KeyError, TypeError):
        return None


def serializer_errors(serializer):
    return [
        {"status": "400", "source": {"pointer": f"/data/attributes/{field}"}, "detail": str(msgs[0])}
        for field, msgs in serializer.errors.items()
    ]
