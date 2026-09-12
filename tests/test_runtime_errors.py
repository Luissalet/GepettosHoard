from backend.runtime import operation_error


def test_download_errors_explain_certificate_failure_without_signed_url():
    message = operation_error(
        ValueError(
            "Get https://cdn.example/file?token=private: tls: failed to verify certificate: x509: certificate signed by unknown authority"
        )
    )
    assert "certificado" in message
    assert "private" not in message and "https://" not in message


def test_other_download_errors_keep_cause_without_url_credentials():
    message = operation_error(
        ValueError("Get https://cdn.example/file?signature=private : connection reset by peer")
    )
    assert "connection reset" in message and "private" not in message
