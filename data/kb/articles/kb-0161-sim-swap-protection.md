---
doc_id: kb-0161
title: SIM swap protection
category: security
section_path: [Security, Devices]
countries: all
effective_date: 2025-01-01
superseded_by: null
article_type: policy
status: draft
mess: [buried_exception, cross_reference]
---
In a SIM swap scam, a criminal convinces your mobile operator to move your number to a new SIM card, so they receive your codes. We watch for this.

## What we do

When we detect that the SIM card for your number has changed, we pause all outgoing transfers, local and international, for {{security.sim_swap_hold.ALL}}. You'll get an email explaining why.

## I changed my SIM myself

That's fine. If you got a new SIM, for example after losing your phone or switching to an eSIM, the pause ends on its own after {{security.sim_swap_hold.ALL}}. To lift it sooner, take a selfie in **Profile** > **Security** > **Confirm it's me**.

## Signs your SIM has been swapped

- Your phone suddenly shows **No service** or **SOS only**, in a place where it normally works.
- You get a message from your operator about a SIM change you didn't ask for.
- You stop receiving calls and texts.

If this happens, contact your mobile operator first, then our fraud line. See [Reporting fraud](kb-0156).

Card payments in shops keep working during the pause, because they don't depend on SMS codes. If you think your SIM was swapped by someone else, freeze your card as well.
