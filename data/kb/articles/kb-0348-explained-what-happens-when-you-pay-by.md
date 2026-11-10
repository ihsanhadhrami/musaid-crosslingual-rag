---
doc_id: kb-0348
title: "Explained: what happens when you pay by card"
category: cards
section_path: [Guides, Explained]
countries: all
effective_date: 2025-01-01
superseded_by: null
article_type: guide
status: draft
mess: [buried_exception, cross_reference]
---
Tapping your card takes a second, but behind it there are several steps, and they explain some things that can look strange in **Activity**.

## 1. Authorization

When you pay, the shop's card machine sends a request through the card network to us. We check that your card is active, that you have enough balance, that the payment is within your limits and card settings, and that it doesn't look like fraud. Then we approve or decline it.

If we approve, the amount is held from your balance straight away. In **Activity**, the payment shows as **Pending**.

## 2. Settlement

Usually within a day or two, the merchant's bank asks for the money. The payment changes from **Pending** to **Completed**. Most of the time the amount is the same.

## Why the amount can change

- **Abroad**, the exchange rate is applied when the payment is settled, not when you paid, so the final amount in your currency can be slightly different.
- **Tips** added after you sign, common in restaurants and taxis abroad, are added at settlement.
- **Hotels, car rental and petrol stations** often authorize an estimated amount and settle the real amount later.

## Holds that disappear

If a merchant authorizes a payment but never settles it, the hold drops off by itself, usually within {{card.hold_release.ALL}}. Hotel and car rental holds can last up to {{card.hold_release_extended.ALL}}. We can't release a hold early; only the merchant can. See [Merchant holds and pre-authorizations](kb-0123).

## Declined payments

A payment can be declined at authorization for many reasons: not enough balance, a card setting switched off, a limit reached, or a fraud check. The app usually tells you why in a notification. See [Card declined](kb-0114).

## Refunds

A refund is a separate payment from the merchant to you. It isn't the original payment being cancelled, so it appears as a new line in **Activity**, and it can take several business days to arrive after the merchant sends it.
