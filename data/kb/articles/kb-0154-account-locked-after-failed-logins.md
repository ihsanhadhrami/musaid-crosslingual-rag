---
doc_id: kb-0154
title: Account locked after failed login attempts
category: security
section_path: [Security, Logging in]
countries: [SA, AE, EG]
effective_date: 2025-01-01
superseded_by: null
article_type: troubleshooting
status: rewritten
mess: [buried_exception]
---
## "Too many attempts. Try again later."

The app temporarily blocks login after {{security.max_login_attempts.ALL}} consecutive incorrect passwords. The lock remains in place for {{security.lockout_duration.ALL}}, after which you can try signing in again.

## If you forgot your password

Stop entering possible passwords and select **Forgot password** on the login screen. Confirm your phone number using the code we send, then create a new password. Completing the reset removes the login lock immediately.

## Does the card continue working?

Yes. The lock applies only to app access. Your physical card and scheduled transfers continue to operate. If you suspect someone is attempting to access your account, freeze the card through the website or call the number printed on its back.

## If the account is locked repeatedly

If your account reaches {{security.lockouts_before_restriction.ALL}} locks in one day, it is placed under an additional security restriction. The normal timer will no longer restore access, and changing your password will not remove the restriction. Support must verify your identity and unlock the account. Contact us through **Help** on the login screen.
