START_TIMESTAMP: 2026-06-12T11:24:09-05:00
ESTIMATE: T2-pre-v2 6m
MESSAGES_USED: 0

## Worker secret-backend env
- DBUS_SESSION_BUS_ADDRESS: set
- gnome-keyring-daemon running: yes
- kwalletd5 running: no
- kwalletd6 running: no

## Preflight
- DISPLAY non-empty: yes
- SingletonLock exists at check: no
- /usr/bin/chromium running at check: no

## Probe results
### Profile 1
- verdict: ambiguous
- snapshot: {'auth_host': False, 'path_root': True, 'path_conversation': False, 'composer': False, 'hist_links': 0, 'model_btn': 0, 'acct_btn': 0, 'login_ctl': 0, 'signup_ctl': 0, 'title_generic': False, 'title_length': 16}
- reason: no confident signal after 20s poll {'auth_host': False, 'path_root': True, 'path_conversation': False, 'composer': False, 'hist_links': 0, 'model_btn': 0, 'acct_btn': 0, 'login_ctl': 0, 'signup_ctl': 0, 'title_generic': False, 'title_length': 16}
### Default
- verdict: ambiguous
- snapshot: {'auth_host': False, 'path_root': True, 'path_conversation': False, 'composer': False, 'hist_links': 0, 'model_btn': 0, 'acct_btn': 0, 'login_ctl': 0, 'signup_ctl': 0, 'title_generic': False, 'title_length': 16}
- reason: no confident signal after 20s poll {'auth_host': False, 'path_root': True, 'path_conversation': False, 'composer': False, 'hist_links': 0, 'model_btn': 0, 'acct_btn': 0, 'login_ctl': 0, 'signup_ctl': 0, 'title_generic': False, 'title_length': 16}

## Conclusion
- Neither profile is signed-in; at least one probe remained ambiguous after robust hydration.
- Next action: Manager/operator should decide from the snapshot facts; no login was automated.
- ZERO prompts sent; no login was automated; audit ledger untouched.
- MESSAGES_USED: 0
SIGNED_IN_PROFILE_DIRECTORY: NONE
END_TIMESTAMP: 2026-06-12T11:25:54-05:00
T2-pre-v2-STATUS: PARTIAL
