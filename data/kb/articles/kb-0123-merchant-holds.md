---
doc_id: kb-0123
title: Merchant holds and pre-authorizations
category: cards
section_path: [Cards, Paying in shops]
countries: all
effective_date: 2025-01-01
superseded_by: null
article_type: faq
status: draft
mess: [buried_exception]
---
Some merchants reserve money on your card before charging you the final amount. This is called a hold or pre-authorization.

## Where do holds happen?

Hotels, car rental, petrol stations, and some online shops and subscriptions that check your card with a small amount.

## What does a hold look like?

A **Pending** payment in **Activity**. The amount is taken from your available balance but hasn't been paid to the merchant.

## When is it released?

When the merchant charges the final amount, the hold is replaced by the real payment. If the merchant doesn't charge anything, the hold drops off on its own within {{card.hold_release.ALL}}.

## Can you release a hold early?

We can't, because the merchant decides. Ask the merchant to cancel the pre-authorization; once they do, the money is usually back within a day.

Hotels and car rental companies are allowed to keep a hold for longer, up to {{card.hold_release_extended.ALL}}, for example to cover damage or extra nights. These holds are released when the merchant closes your booking, not after the standard time.
