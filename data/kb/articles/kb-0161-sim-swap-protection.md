---
doc_id: kb-0161
title: SIM swap protection
category: security
section_path: [Security, Devices]
countries: all
effective_date: 2025-01-01
superseded_by: null
article_type: policy
status: rewritten
mess: [buried_exception, cross_reference]
---
A SIM swap occurs when someone persuades your mobile operator to move your phone number to another SIM, allowing them to receive your verification codes. We monitor for this type of change.

## Protection after a SIM change

When we detect that your number has been moved to a different SIM, outgoing transfers, including local and international transfers, are paused for {{security.sim_swap_hold.ALL}}. We send an email explaining the hold.

## If you changed the SIM yourself

The protection is also triggered by legitimate changes, such as replacing a lost-phone SIM or moving to an eSIM. In that case, the pause ends automatically after {{security.sim_swap_hold.ALL}}.

You can request earlier access by completing **Profile** > **Security** > **Confirm it's me** and taking a selfie.

## Signs of a possible SIM swap

Watch for:

- **No service** or **SOS only** appearing where your phone normally has coverage.
- A mobile-operator notification about a SIM replacement you did not request.
- An unexpected loss of incoming calls and text messages.

If you notice these signs, contact your mobile operator first and then call our fraud line. See [Reporting fraud](kb-0156).

Card payments in shops continue to work during the transfer hold because they do not rely on SMS verification. If you suspect another person performed the SIM swap, freeze your card as well.
