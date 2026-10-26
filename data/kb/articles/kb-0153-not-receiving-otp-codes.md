---
doc_id: kb-0153
title: Not receiving OTP codes
category: security
section_path: [Security, Logging in]
countries: all
effective_date: 2025-01-01
superseded_by: null
article_type: troubleshooting
status: draft
mess: [buried_exception, cross_reference]
---
One-time passwords are sent by SMS to your registered phone number. If they're not arriving, try these steps in order.

## Quick checks

1. Make sure your phone has signal. Turn airplane mode on and off.
2. Check that the number in the app is the one in your phone. You'll see the last digits on the code screen.
3. Look in your SMS spam or blocked messages folder.
4. If your phone storage is full, delete some messages.

## Resending the code

Wait {{security.otp_resend_wait.ALL}}, then tap **Resend code**. You can resend up to {{security.otp_max_resends.ALL}} times. After that, you'll need to wait {{security.otp_resend_lockout.ALL}} before trying again.

## Abroad?

Codes are sent to your number while you're roaming, but some networks abroad delay or block them. Turn on roaming, or connect to Wi-Fi and use the in-app approval if you're already logged in.

## Changed your number?

You need to update it first; see [Changing your registered phone number](kb-0013).

If you suddenly stop receiving codes and your phone shows no signal at all, your SIM may have been swapped by someone else. Call your mobile operator immediately, and see [SIM swap protection](kb-0161).
