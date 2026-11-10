---
doc_id: kb-0010
title: Unverified vs verified accounts
category: account_kyc
section_path: [Account, Verification]
countries: all
effective_date: 2026-03-01
superseded_by: null
article_type: policy
status: rewritten
mess: [country_specific, cross_reference]
---
All new Sahla Pay accounts begin in the unverified tier. Completing identity verification increases the applicable limits and enables additional services.

| Feature | Unverified | Verified |
|---|---|---|
| Receive money and add funds | Yes | Yes |
| Send to other Sahla Pay users | Yes, subject to lower limits | Yes |
| Send to bank accounts | No | Yes |
| International transfers | No | Yes, except for Egypt-registered accounts |
| Virtual and physical cards | No | Yes |

## Limits by registered country

| | Saudi Arabia | UAE | Egypt |
|---|---|---|---|
| Maximum balance, unverified | {{limits.balance_max_unverified.SA}} | {{limits.balance_max_unverified.AE}} | {{limits.balance_max_unverified.EG}} |
| Maximum balance, verified | {{limits.balance_max_verified.SA}} | {{limits.balance_max_verified.AE}} | {{limits.balance_max_verified.EG}} |
| Daily sending, unverified | {{limits.daily_transfer_unverified.SA}} | {{limits.daily_transfer_unverified.AE}} | {{limits.daily_transfer_unverified.EG}} |
| Daily sending, verified | {{limits.daily_transfer_verified.SA}} | {{limits.daily_transfer_verified.AE}} | {{limits.daily_transfer_verified.EG}} |

An incoming payment is rejected if it would push an unverified account above its maximum balance. The sender's money is then returned.

For the full transfer rules, see [Daily and monthly transfer limits](kb-0034). To complete verification, follow [How to verify your identity in the app](kb-0006).
