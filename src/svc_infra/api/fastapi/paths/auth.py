# --- API KEYS ---
LIST_KEYS_PATH = "/keys"
CREATE_KEY_PATH = "/keys"
REVOKE_KEY_PATH = "/keys/{key_id}/revoke"
DELETE_KEY_PATH = "/keys/{key_id}"

# --- MFA ---
MFA_START_PATH = "/mfa/start"
MFA_CONFIRM_PATH = "/mfa/confirm"
MFA_DISABLE_PATH = "/mfa/disable"
MFA_STATUS_PATH = "/mfa/status"
MFA_REGENERATE_RECOVERY_PATH = "/mfa/recovery/regenerate"
MFA_VERIFY_PATH = "/mfa/verify"
MFA_SEND_CODE_PATH = "/mfa/send_code"

# --- OAUTH ---
OAUTH_LOGIN_PATH = "/{provider}/login"
OAUTH_CALLBACK_PATH = "/{provider}/callback"
OAUTH_REFRESH_PATH = "/refresh"
