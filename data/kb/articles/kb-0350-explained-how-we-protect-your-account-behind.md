---
doc_id: kb-0350
title: "Explained: how we protect your account behind the scenes"
category: security
section_path: [Guides, Explained]
countries: all
effective_date: 2025-01-01
superseded_by: null
article_type: guide
status: draft
mess: [buried_exception, cross_reference]
---
Some of our security is visible: codes, passwords and fingerprints. Much of it you never see. Here's what's happening in the background.

## Your phone is part of your security

When you log in on a phone and confirm it's you, that phone becomes a trusted device. Logging in on a new phone needs an SMS code and a selfie check, and for a while afterwards, transfers to new recipients and international transfers are paused. This means someone who steals your password still can't move money from their own phone straight away. See [Trusted devices](kb-0160).

## We watch for SIM swaps

Some fraudsters persuade a mobile operator to move your number to their SIM, so they receive your codes. We detect when your number moves to a new SIM, and pause outgoing transfers for {{security.sim_swap_hold.ALL}}. See [SIM swap protection](kb-0161).

## We look at how payments are made

Every payment is checked automatically against your usual activity: the amount, the recipient, the device, the location of your connection and the time of day. Payments that look very different from your normal pattern may need extra approval, or may be held for review.

This is also why a VPN can cause problems. It can make it look as if you're logging in from another country. See [Using Sahla Pay with a VPN](kb-0187).

## We tell you about important changes

You get an alert by notification, SMS and email when:

- someone logs in on a new device;
- your password, phone number or email changes;
- a new trusted device is added.

If you didn't do it, tap **This wasn't me** in the alert. See [Suspicious login alerts](kb-0163).

## What we can't do for you

None of this helps if you share a one-time password with someone. If a payment is approved with your code, it looks exactly like a payment you made. That's why we say it so often: nobody from Sahla Pay will ever ask for your code.
