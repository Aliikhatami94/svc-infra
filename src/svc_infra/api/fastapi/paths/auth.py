# --- API KEYS ---
LIST_KEYS_PATH = "/auth/keys"
CREATE_KEY_PATH = "/auth/keys"
REVOKE_KEY_PATH = "/auth/keys/{key_id}/revoke"
DELETE_KEY_PATH = "/auth/keys/{key_id}"

# --- MFA ---
MFA_START_PATH = "/auth/mfa/start"
MFA_CONFIRM_PATH = "/auth/mfa/confirm"
MFA_DISABLE_PATH = "/auth/mfa/disable"
MFA_STATUS_PATH = "/auth/mfa/status"
MFA_REGENERATE_RECOVERY_PATH = "/auth/mfa/recovery/regenerate"
MFA_VERIFY_PATH = "/auth/mfa/verify"
MFA_SEND_CODE_PATH = "/auth/mfa/send_code"

# --- OAUTH ---
OAUTH_LOGIN_PATH = "/auth/oauth/{provider}/login"
OAUTH_CALLBACK_PATH = "/auth/oauth/{provider}/callback"
OAUTH_REFRESH_PATH = "/auth/oauth/refresh"
