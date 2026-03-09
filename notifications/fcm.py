"""Firebase Cloud Messaging utility for push notifications.

Sends FCM push notifications to all active devices for a user.
Gracefully no-ops if Firebase credentials are not configured.
"""

import base64
import json
import logging
import os
import threading

logger = logging.getLogger(__name__)

_firebase_app = None
_firebase_init_attempted = False
_firebase_init_lock = threading.Lock()


def _get_firebase_app():
    """Lazy-initialize Firebase Admin SDK.

    Reads credentials from FIREBASE_SERVICE_ACCOUNT (base64-encoded JSON)
    or FIREBASE_SERVICE_ACCOUNT_FILE (path to JSON file).
    Returns None if credentials are not configured.
    Thread-safe via lock.
    """
    global _firebase_app, _firebase_init_attempted

    if _firebase_init_attempted:
        return _firebase_app

    with _firebase_init_lock:
        # Double-checked locking
        if _firebase_init_attempted:
            return _firebase_app

        try:
            import firebase_admin  # type: ignore
            from firebase_admin import credentials
        except ImportError:
            logger.info("firebase-admin not installed, push notifications disabled")
            _firebase_init_attempted = True
            return None

        # Check for existing app first
        try:
            _firebase_app = firebase_admin.get_app()
            _firebase_init_attempted = True
            return _firebase_app
        except ValueError:
            pass

        # Try base64-encoded service account JSON
        sa_b64 = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        if sa_b64:
            try:
                sa_json = json.loads(base64.b64decode(sa_b64))
                cred = credentials.Certificate(sa_json)
                _firebase_app = firebase_admin.initialize_app(cred)
                logger.info(
                    "Firebase Admin SDK initialized from FIREBASE_SERVICE_ACCOUNT"
                )
                _firebase_init_attempted = True
                return _firebase_app
            except Exception:
                logger.exception(
                    "Failed to initialize Firebase from FIREBASE_SERVICE_ACCOUNT"
                )
                _firebase_init_attempted = True
                return None

        # Try file path
        sa_file = os.environ.get("FIREBASE_SERVICE_ACCOUNT_FILE")
        if sa_file:
            try:
                cred = credentials.Certificate(sa_file)
                _firebase_app = firebase_admin.initialize_app(cred)
                logger.info(
                    "Firebase Admin SDK initialized from FIREBASE_SERVICE_ACCOUNT_FILE"
                )
                _firebase_init_attempted = True
                return _firebase_app
            except Exception:
                logger.exception(
                    "Failed to initialize Firebase from FIREBASE_SERVICE_ACCOUNT_FILE"
                )
                _firebase_init_attempted = True
                return None

        logger.info("No Firebase credentials configured, push notifications disabled")
        _firebase_init_attempted = True
        return None


def send_push_to_user(user_id, title, body, data=None):
    """Send FCM push notification to all active devices for a user.

    Args:
        user_id: The recipient user's ID
        title: Notification title
        body: Notification body text
        data: Optional dict of string key-value pairs for data payload

    Returns:
        Number of messages successfully sent
    """
    app = _get_firebase_app()
    if app is None:
        return 0

    try:
        from firebase_admin import messaging
    except ImportError:
        return 0

    from .models import DeviceToken

    tokens = list(
        DeviceToken.objects.filter(user_id=user_id, is_active=True).values_list(
            "token", "platform"
        )
    )

    if not tokens:
        return 0

    # Ensure data values are strings (FCM requirement)
    str_data = {k: str(v) for k, v in (data or {}).items()}
    str_data["title"] = title
    str_data["body"] = body

    messages = []
    token_list = []
    for token, platform in tokens:
        if platform == DeviceToken.Platform.ANDROID:
            # Data-only message for Android — app handles display
            msg = messaging.Message(
                data=str_data,
                token=token,
            )
        else:
            # Notification+data hybrid for web (shows even when SW handles it)
            msg = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data=str_data,
                token=token,
            )
        messages.append(msg)
        token_list.append(token)

    # Batch send all messages at once
    try:
        response = messaging.send_each(messages, app=app)
    except Exception:
        logger.exception("FCM send_each failed")
        return 0

    sent = 0
    stale_tokens = []
    for i, send_response in enumerate(response.responses):
        if send_response.success:
            sent += 1
        else:
            error_code = getattr(send_response.exception, "code", "")
            if error_code in ("NOT_FOUND", "UNREGISTERED", "INVALID_ARGUMENT"):
                stale_tokens.append(token_list[i])
                logger.info("Deactivated stale FCM token: %s", token_list[i][:20])
            else:
                logger.warning(
                    "FCM send failed for token %s: %s",
                    token_list[i][:20],
                    send_response.exception,
                )

    if stale_tokens:
        DeviceToken.objects.filter(token__in=stale_tokens).update(is_active=False)

    return sent
