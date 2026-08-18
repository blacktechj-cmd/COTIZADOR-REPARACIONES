"""Compatibility fixes loaded automatically by Python before Streamlit starts."""

import io

try:
    from pypdf import PdfReader as _PdfReader

    _original_init = _PdfReader.__init__

    def _bytesafe_init(self, stream, strict=False, password=None):
        # Streamlit UploadedFile.getvalue() returns bytes. pypdf expects a
        # seekable stream, so wrap bytes before handing them to pypdf.
        if isinstance(stream, (bytes, bytearray, memoryview)):
            stream = io.BytesIO(bytes(stream))
        return _original_init(self, stream, strict=strict, password=password)

    _PdfReader.__init__ = _bytesafe_init
except Exception:
    # Do not prevent the application from starting if pypdf is unavailable.
    pass
